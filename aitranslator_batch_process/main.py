###
# Languages in the database must use the ISO 639-1 format
# https://gist.github.com/alexanderjulo/4073388
###


import os
import re
import time
import pycountry
import bisect
import psycopg2

from datetime import datetime, timezone
from typing import Optional, List

from dotenv import load_dotenv
from pathlib import Path
import xml.etree.ElementTree as ET

from llm_einstein_manager import LLM_Einstein_Manager
from logger_manager import LoggerManager
from xliff_file_manager import XliffManager


# Prompt template for LLM
PROMPT_TEMPLATE = """
INSTRUCTIONS

You are receiving a list of {llm_batch_size} <trans-unit> XML elements. 
Each <trans-unit> instance will contain the following elements:
- id: A unique identifier for the <trans-unit>.
- maxwidth: maximum character width for the translation.
- size-unit: the unit of the maxwidth attribute.
- source: the original text to be translated.
- target: an example of a translated value into another language.

Your task is to provide the same list of <trans-units> but in the <target> node you must provide the translation of the text in the <source> node into {language}.
For example, for the following <trans-unit> element:
<trans-unit id="CustomLabel.Text" maxwidth="240">
<source>Advanced Editor</source>
<target>Erweiterter Editor</target>
</trans-unit>

The expected answer from you is:
<trans-unit id="CustomLabel.Text" maxwidth="240">
<source>Advanced Editor</source>
<target></target> <-- THIS TARGET NODE SHOULD CONTAIN THE TRANSLATION TO {language} of the <source> node.
</trans-unit>

So, the only change expected in every <trans-unit> is the <target> node, with will contain translation of the source text into {language}.

Follow these guidelines:
- Do not add any header and neither number the lines.
- Do not miss any <trans-unit> element.
- Do not change the id, maxwidth, or size-unit attributes.
- Use professional healthcare terminology for translation as appropriate for healthcare professionals.
- The translation should not exceed the maxwidth characters.
- For HTML-like content, translate only the visible text, leaving any markup intact.
- If the text includes double quotes, leave them unchanged.
- Words in CAPITAL LETTERS should remain in capital letters in the translation.
- Translate all <trans-unit> elements without omitting any.

Also, when translating consider the following particularities:
{prompt_addition}

-----------
This is the list of sequence of <trans-unit> sequence:

{list}
"""


# DB Operations 
# Fetch all pending translation requests
def fetch_pending_requests(cursor):
    cursor.execute("SELECT id, language_id, project_id, source_xliff_file, target_xliff_file_name, literals_to_exclude_file, literalpatterns_to_exclude_file, status\
                    FROM xliff_manager_translationsrequests WHERE status='Created'")
    
    pending_trans_requests = cursor.fetchall()
    return pending_trans_requests

# Fetch custom instructions for the translation request
def fetch_custom_instructions(cursor, language_id):
    cursor.execute("SELECT instructions \
                    FROM xliff_manager_custominstructions \
                    WHERE language_id=%s", (language_id,))
    
    custom_instructions = cursor.fetchone()
    return custom_instructions[0] if custom_instructions else None

# Fetch the target language ISO value
def fetch_target_language_iso(cursor, language_id):
    cursor.execute("SELECT lang_iso_value \
                    FROM xliff_manager_languages \
                    WHERE id=%s", (language_id,))
    target_language_iso = cursor.fetchone()[0]
    return target_language_iso

def update_translation_request_status(cursor, status, date_started_on_llm, date_received_from_llm, id):
    cursor.execute("UPDATE xliff_manager_translationsrequests\
                    SET status = %s, date_started_on_llm=%s, date_received_from_llm=%s\
                    WHERE id=%s",\
                    (status, date_started_on_llm, date_received_from_llm, str(id)))

def update_diary(cursor, user_id, project_id, date, action, translation_request_id, additional_info):    
    cursor.execute("INSERT INTO xliff_manager_logdiary\
                    (user_id, date, action, project_id, translation_request_id, additional_info)\
                    VALUES (%s, %s, %s, %s, %s, %s)",\
                    (user_id, date, action, project_id, translation_request_id, additional_info))

def prepare_prompt(rows, language_iso, prompt_addition, llm_batch_size):
    translation_request_rows = "\n".join(rows)
    target_language = (pycountry.languages.get(alpha_2=language_iso).name if language_iso else "Not target language found"
    )
    prompt = PROMPT_TEMPLATE.format(
        llm_batch_size=llm_batch_size,
        language=target_language,
        prompt_addition=prompt_addition,
        list=translation_request_rows,
    )
    return prompt

def filter_excluded_trans_units(trans_units, excluded_ids, exclusion_patterns):

    logger = logger_manager.get_logger()
    logger.info("\t->Filtering excluded literals - the exclusions file must be sorted alphabetically ...")

    trans_units_excluded = []
    trans_units_not_excluded = []

    # We'll try to exclude by pattern or by list
    for trans_unit in trans_units:
        
        # Extract the 'id' attribute from <trans-unit> using regex
        match = re.search(r'<trans-unit id="([^"]+)"', trans_unit)
  
        if match:
            trans_unit_id = match.group(1)  # Extract the ID

            # Check if the trans_unit_id starts with any of the excluded patterns
            if any(trans_unit_id.startswith(pattern) for pattern in exclusion_patterns):
               trans_units_excluded.append(trans_unit) 
            else:
                # Perform binary search to check if the ID is in the exclusion list
                # excluded_ids is mandatory to be sorted for binary search to work properly
                idx = bisect.bisect_left(excluded_ids, trans_unit_id)
                if idx < len(excluded_ids) and excluded_ids[idx] == trans_unit_id:
                    trans_units_excluded.append(trans_unit)
                else:
                    trans_units_not_excluded.append(trans_unit)
        else:
            logger.error("The id couldn't be found when trying to exclude, this is not an error, but it is inefficient, as we don't know if this literal would be exluded from translation")

    logger.info(f"\t->From {len(trans_units)} trans_units, Excluded: {len(trans_units_excluded)}, Not Excluded: {len(trans_units_not_excluded)}")
    
    return trans_units_not_excluded, trans_units_excluded


def process_batch(prompt, request_folder, batch_number):

    logger = logger_manager.get_logger()

    # Call the Einstein LLM
    llm_einstein_manager = LLM_Einstein_Manager(_CLIENT_ID, _CLIENT_SECRET, _TOKEN_URL)
    llm_response = llm_einstein_manager.call_llm(prompt)
    
    if not llm_response:
        logger.error("No translations were generated. Skipping this batch.")
        raise ValueError("No translations were generated. Skipping this batch.")

    # Save the request for tracking purposes
    partial_files_folder = os.path.normpath(os.path.join(request_folder, 'partial_files'))
    if not os.path.exists(partial_files_folder):
        os.makedirs(partial_files_folder)

    request_path = os.path.normpath(os.path.join(partial_files_folder, f'{batch_number}-Request.txt'))
    request_dir = os.path.dirname(request_path)
    if not os.path.exists(request_dir):
        os.makedirs(request_dir)

    with open(request_path, "w", encoding="utf-8") as file:
        file.write(prompt)

    # Save the response
    response_path = os.path.normpath(os.path.join(request_folder, 'partial_files', f'{batch_number}-Response.txt'))
    with open(response_path, "w", encoding="utf-8") as file:
        file.write(llm_response)

    logger.info(f"Saving partial files to: {request_path} and to: {response_path}")

def translate(
    request_id: int,
    request_folder: str,
    source_xliff_file: str,
    target_xlf_file_name: str,
    target_language_iso: str,
    llm_batch_size: Optional[int] = 100,
    prompt_addition_custom_instructions: str = "",
    excluded_literals_file_name: str = "",
    exclusion_patterns_file_name: str = "",
    concrete_batches_to_execute: List[int] = []
) -> str:
    try:
        logger = logger_manager.get_logger()

        source_xlf_file_path = os.path.join(request_folder, source_xliff_file)
        target_xlf_file_path = os.path.join(request_folder, target_xlf_file_name)
        target_xlf_file_baseline_path = None

        if not os.path.exists(source_xlf_file_path):
            logger.error(f"Source XLIFF file not found in: {source_xlf_file_path}")
            raise FileNotFoundError(f"Source XLIFF file not found in: {source_xlf_file_path}")
        
        excluded_literals = ""
        if excluded_literals_file_name is not None and excluded_literals_file_name:
            excluded_literals_file_path = os.path.join(request_folder, excluded_literals_file_name),
            if not os.path.exists(excluded_literals_file_path[0]):
                logger.error(f"Excluded literals file not found: {excluded_literals_file_path[0]}")
            with open(excluded_literals_file_path[0], "r", encoding="utf-8") as file:
                excluded_literals = sorted({line.strip() for line in file if line.strip()})
            logger.info(f"Loaded {len(excluded_literals)} excluded literals.")
        
        # Load in a set the exclusion patterns file, if there are any
        exclusion_patterns = ""
        if exclusion_patterns_file_name is not None and exclusion_patterns_file_name:
            exclusion_patterns_file_path = os.path.join(request_folder, exclusion_patterns_file_name),
            with open(exclusion_patterns_file_path[0], "r", encoding="utf-8") as file:
                exclusion_patterns = file.read().split(",")
            logger.info(f"Loaded {len(exclusion_patterns)} exclusion patterns.")

        tree = xliff_manager.parse_file(source_xlf_file_path, log_stats=True)
        if tree:
            rows_to_translate = xliff_manager.get_only_trans_units_with_target(tree)

        # Split trans_units into batches of the specified size, as we can't call the LLM with an infinite window context
        # Find all the <trans-unit> tags in the data
        trans_units = re.findall(r"<trans-unit.*?</trans-unit>", rows_to_translate, re.DOTALL)

        # Apply exclusions if required
        trans_units_without_exclusions = trans_units
        trans_units_excluded = None
        if excluded_literals or exclusion_patterns:
            trans_units_without_exclusions, trans_units_excluded = filter_excluded_trans_units(trans_units, excluded_literals, exclusion_patterns)

        batches = [
            trans_units_without_exclusions[i : i + llm_batch_size]
            for i in range(0, len(trans_units_without_exclusions), llm_batch_size)
        ]
        logger.info(f"\t ->Batches: {len(batches)} of {llm_batch_size} trans-units each.")

        # Create all the batches or only some concrete (probably re-batching of failing batches in a previous run)
        total_rows = 0
        for batch_number, batch_rows in enumerate(batches, start=1):

            if (not concrete_batches_to_execute or batch_number in concrete_batches_to_execute):
                logger.info(f"Batch {batch_number}/{len(batches)} to be processed.")
                prompt = prepare_prompt(
                    batch_rows, target_language_iso, prompt_addition_custom_instructions, llm_batch_size
                )
                batch_number = f"{batch_number:03}"  # Convert batch_number to a 3-digit number
                process_batch(prompt, request_folder, batch_number)
            else:
                logger.info(f"Skipping batch {batch_number}")

            total_rows += len(batch_rows)
        
        # Generate the new file
        generated_file = xliff_manager.create_translations_xlif_file(request_folder, target_xlf_file_path, target_xlf_file_baseline_path, target_language_iso)
        return generated_file
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        pass
    

def execute_pending_requests():

    try:
        conn = psycopg2.connect(
            host     = DATABASE_HOST,
            port     = DATABASE_PORT,
            dbname   = DATABASE_DATABASE,
            user     = DATABASE_USER,
            password = DATABASE_PASSWORD
        )
        conn.autocommit = False # allows to rollback in case of error
        cursor = conn.cursor()

        pending_trans_requests = fetch_pending_requests(cursor)
        logger.info(f"Processing {len(pending_trans_requests)} pending translation requests...")

        for trans_request in pending_trans_requests:
            # Assuming the columns are in the order: id, language_id, project_id, source_xliff_file, target_xliff_file_name, excluded_literals_file_path, exclusion_patterns_file_path, language_id, status
            id, language_id, project_id, source_xliff_file, target_xliff_file_name, literals_to_exclude_file, literalpatterns_to_exclude_file, status = trans_request

            prompt_addition_custom_instructions = fetch_custom_instructions(cursor, language_id)
            target_language_iso = fetch_target_language_iso(cursor, language_id)

            try: 
                started_on_llm = datetime.now(timezone.utc).isoformat()
                update_translation_request_status(cursor = cursor, status = 'Started_on_LLM', date_started_on_llm = started_on_llm, date_received_from_llm = None, id = id)
                update_diary(cursor = cursor, user_id = 1, project_id=project_id, date= started_on_llm, action = "Translation_Started_on_AI", translation_request_id = id, additional_info = '🤖 LLM started processing the request')
                conn.commit()

                translation_file_generated = translate(
                    request_id = id,
                    request_folder = os.path.join(TRANS_REQUESTS_FOLDER, str(id)),
                    source_xliff_file = source_xliff_file,
                    target_xlf_file_name = target_xliff_file_name,
                    target_language_iso = target_language_iso,
                    prompt_addition_custom_instructions = prompt_addition_custom_instructions,
                    excluded_literals_file_name = literals_to_exclude_file,
                    exclusion_patterns_file_name = literalpatterns_to_exclude_file,
                )

            except Exception as e:
                received_from_llm = datetime.now(timezone.utc).isoformat()
                logger.error(f"Error reading the XLIFF file: {e}")
                logger.info(f"Should be skipping the request {id} as it is not possible to process it and keep with the rest of the requests.")
                # Update the status of the translation request
                update_translation_request_status(cursor = cursor, status = 'Error_from_AI', date_started_on_llm = None, date_received_from_llm = received_from_llm, id = id)
                conn.commit()
                continue

            received_from_llm = datetime.now(timezone.utc).isoformat()
            if translation_file_generated is not None:
                logger.info(f"Translation request {id} has been processed successfully")

                # Update the status of the translation request
                update_translation_request_status(cursor = cursor, status = 'Received_from_LLM', date_started_on_llm = started_on_llm, date_received_from_llm = received_from_llm, id = id)
                update_diary(cursor = cursor, user_id = 1, project_id=project_id, date= received_from_llm, action = "Translation_Received_from_AI", translation_request_id = id, additional_info = "🤖 LLM finished processing the request")
                conn.commit()
            else:
                logger.error(f"An error occurred while translating the request {id}. The request will be marked as 'Error' and no translation has been generated.")
                update_translation_request_status(cursor = cursor, status = 'Error_from_AI', date_started_on_llm = started_on_llm, date_received_from_llm = received_from_llm, id = id)
                conn.commit()

    except psycopg2.DatabaseError as e:
        logger.error("An error occurred while trying to connect the database: {e}")
    
    except psycopg2.OperationalError:
        logger.error("An error occurred while accessing the database (malformed query, lock, etc)")
    
    except psycopg2.IntegrityError:
        logger.error("An error occurred while trying to insert data into the database (Violating a unique constraint, not-null constraint, foreign key constraint etc)")
    
    except psycopg2.ProgrammingError:
        logger.error("An error occurred while trying to execute a query that has a syntax error or a query that is not supported by the database.")

    except psycopg2.NotSupportedError:
        logger.error("An error occurred while trying to execute a query that the database doesn't support.")
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    

if __name__ == "__main__":

    # Global variables
    global logger_manager
    global xliff_manager

    # Initialize logger and XLIFF manager
    logger_manager = LoggerManager()
    xliff_manager = XliffManager()

    logger = logger_manager.get_logger()
    logger.info("Starting the translation process...")

    # Load environment variables from .env file 
    # #TODO això realment cal, si ja ho estem fent a settings.py?
    is_dev = os.environ.get("IS_DEVELOPMENT_ENV")
    if is_dev == "TRUE":
        dotenv_path = ".env.prod"
        DEBUG = False
    else:
        dotenv_path = ".env.dev"
        DEBUG = True

    if not os.path.exists(dotenv_path):
        logger.error(f"Environment file not found: {dotenv_path}")
        raise FileNotFoundError(f"Environment file not found: {dotenv_path}")
    else:
        logger.info(f"Loading environment variables from: {dotenv_path}")
        load_dotenv()

    BACKEND_LOG_FILE = os.environ.get("LOG_FILE_BACKEND")
    with open(BACKEND_LOG_FILE, "a") as f:
        f.write(f"Hearthbit: {datetime.now(timezone.utc).isoformat()}\n")

    DATABASE_HOST     = os.environ.get("DATABASE_HOST")
    DATABASE_PORT     = os.environ.get("DATABASE_PORT")
    DATABASE_DATABASE = os.environ.get("DATABASE_NAME")
    DATABASE_USER     = os.environ.get("DATABASE_USERNAME")
    DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", "")

    TRANS_REQUESTS_FOLDER = os.path.join('media', os.environ.get("TRANS_REQUESTS_FOLDER", ""))

    _CLIENT_ID = os.environ.get("CLIENT_ID", "")
    _CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
    _TOKEN_URL = os.environ.get("TOKEN_URL", "")

    logger.info(f"PostgreSQL settings - {DATABASE_DATABASE} host:port-> {DATABASE_HOST}:{DATABASE_PORT}")

    # In the real scenario, need to be scheduled every X minutes
    execute_pending_requests()
