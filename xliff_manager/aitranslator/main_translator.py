# HOW TO USE it: look at the end of this file

import os
import re
import time
import pycountry
import logging
import bisect
import glob
import shutil
import sys
import time

from typing import Optional, List

from openai import OpenAI
from dotenv import load_dotenv
from xml.dom import minidom
from pathlib import Path
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils

from envvariable_manager import EnvVariableManager
from llm_einstein_manager import LLM_Einstein_Manager
from logger_manager import LoggerManager
from xliff_file_manager import XliffManager

import sqlite3

# Using an OpenAI Compatible LLM or Mistral
#from llm_openai_manager import LLMOpenAIManager

# Using Mistral LLM
#from llm_mistral_manager import LLMMistralAIManager


# Global variables
global logger_manager
global xliff_manager
ROOT_FOLDER = r"c:\code\PoC-SF-Translations\biz-app\xliff_project\translations_requests" #Should be externalized with the one in views.py


# Initialize logger and XLIFF manager
logger_manager = LoggerManager()
xliff_manager = XliffManager()


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


def process_batch(request_folder, batch_number, batch_rows, target_language_iso, prompt_addition, llm_batch_size):

    logger = logger_manager.get_logger()

    # Convert batch_number to a 3-digit number
    batch_number = f"{batch_number:03}"

    # Prepare the prompt with all the rows in the batch
    prompt = prepare_prompt(
        batch_rows, target_language_iso, prompt_addition, llm_batch_size
    )

    # Call the Einstein LLM
    env_manager = EnvVariableManager(logger_manager)
    llm_einstein_manager = LLM_Einstein_Manager(env_manager._CLIENT_ID, env_manager._CLIENT_SECRET, env_manager._TOKEN_URL)
    llm_response = llm_einstein_manager.call_llm(prompt)
    
    # Call any OpenAI API compatible LLM
    #_OPENAI_API_KEY = env_manager._OPENAI_API_KEY
    #_OPENAI_MODEL = env_manager._OPENAI_MODEL
    #llm_openai_manager = LLMOpenAIManager(api_key=_OPENAI_API_KEY, openai_llm=_OPENAI_MODEL)
    #llm_response= llm_openai_manager.call_llm(prompt)
    
    if not llm_response:
        logger.error("No translations were generated. Skipping this batch.")
        raise ValueError("No translations were generated. Skipping this batch.")

    # Save the request for tracking purposes
    os.makedirs(os.path.join(request_folder, 'partial_files'), exist_ok=True)

    request_path = os.path.normpath(os.path.join(request_folder, 'partial_files', f'{batch_number}-Request.txt'))
    with open(request_path, "w", encoding="utf-8") as file:
        file.write(prompt)

    # Save the response
    response_path = os.path.normpath(os.path.join(request_folder, 'partial_files', f'{batch_number}-Response.txt'))
    with open(response_path, "w", encoding="utf-8") as file:
        file.write(llm_response)


def translate(
    request_id: int,
    request_folder: str,
    source_xliff_file: str,
    target_xlf_file_name: str,
    target_language_iso: str,
    llm_batch_size: Optional[int] = 100,
    prompt_addition_file_name: str = "",
    excluded_literals_file_name: str = "",
    exclusion_patterns_file_name: str = "",
    concrete_batches_to_execute: List[int] = []
) -> str:

    logger = logger_manager.get_logger()
    env_manager = EnvVariableManager(logger_manager)

    source_xlf_file_path = os.path.join(request_folder, source_xliff_file)
    target_xlf_file_path = os.path.join(request_folder, target_xlf_file_name)
    target_xlf_file_baseline_path = None

    # Load the prompt addition file
    prompt_addition_text = ""
    if prompt_addition_file_name is not None and prompt_addition_file_name:
        prompt_addition_file_path = os.path.join(request_folder, prompt_addition_file_name),
        with open(prompt_addition_file_path[0], "r", encoding="utf-8") as file:
            prompt_addition_text = {line.strip() for line in file if line.strip()}
        logger.info(f"Loaded prompt addition texts: {len(prompt_addition_text)}")

    excluded_literals = ""
    if excluded_literals_file_name is not None and excluded_literals_file_name:
        excluded_literals_file_path = os.path.join(request_folder, excluded_literals_file_name),
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
            process_batch(request_folder, batch_number, batch_rows, target_language_iso, prompt_addition_text, llm_batch_size)
        else:
            logger.info(f"Skipping batch {batch_number}")

        total_rows += len(batch_rows)
    
    # Generate the new file
    generated_file = xliff_manager.create_translations_xlif_file(request_folder, target_xlf_file_path, target_xlf_file_baseline_path, target_language_iso)

    return generated_file
    

def execute_pending_requests():
    # Connect to the SQLite database
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()

    # Fetch all pending translation requests
    cursor.execute("SELECT id, language_id, source_xliff_file, target_xliff_file_name, prompt_addition_file, literals_to_exclude_file, literalpatterns_to_exclude_file, status  FROM xliff_manager_translationsrequests WHERE status='Created'")
    pending_trans_requests = cursor.fetchall()

    logger = logger_manager.get_logger()
    logger.info(f"Processing {len(pending_trans_requests)} pending translation requests...")

    for trans_request in pending_trans_requests:
        # Assuming the columns are in the order: id, source_xliff_file, target_xliff_file_name, prompt_addition_file_path, excluded_literals_file_path, exclusion_patterns_file_path, language_id, status
        id, language_id, source_xliff_file, target_xliff_file_name, prompt_addition_file, literals_to_exclude_file, literalpatterns_to_exclude_file, status = trans_request

        # Fetch the target language ISO value
        cursor.execute("SELECT iso_value FROM xliff_manager_languages WHERE id=?", str(language_id))
        target_language_iso = cursor.fetchone()[0]

        translation_file_generated = translate(
            request_id = id,
            request_folder = os.path.join(ROOT_FOLDER, str(id)),
            source_xliff_file = source_xliff_file,
            target_xlf_file_name = target_xliff_file_name,
            target_language_iso = target_language_iso,
            prompt_addition_file_name = prompt_addition_file,
            excluded_literals_file_name = literals_to_exclude_file,
            exclusion_patterns_file_name = literalpatterns_to_exclude_file,
        )

        # Update the status of the translation request
        cursor.execute("UPDATE xliff_manager_translationsrequests SET status='Received_from_LLM', date_received_from_llm=? WHERE id=?", (time.strftime('%Y-%m-%d %H:%M:%S'), str(id)))
        

        # Update the LogDiary with this request solved
        additional_info = f"The request Id: {id} has been resolved by the LLM.\
              The files are source:{source_xliff_file}, target:{target_xliff_file_name},\
              prompt_addition: {prompt_addition_file if prompt_addition_file else "-"},\
              literals to exclude: {literals_to_exclude_file if literalpatterns_to_exclude_file else "-"},\
              literal patterns to exclude: {literalpatterns_to_exclude_file if literalpatterns_to_exclude_file else "-"}\
              The user assigned is 1 but it is unrelated."

        current_time = time.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("INSERT INTO xliff_manager_logdiary (user_id, date, action, translation_request_id, additional_info, description) VALUES (?,    ?, ?, ?, ?, ?)", (1, current_time, "Translation_Received_from_LLM", id, additional_info, additional_info))

        conn.commit()

    # Close the database connection
    conn.close()

if __name__ == "__main__":

    # In the real scenario, need to be scheduled every X minutes
    execute_pending_requests()
