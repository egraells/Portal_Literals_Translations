import re
import os
import json
import logging
import xml.etree.ElementTree as ET
import glob
from logger_manager import LoggerManager
from bs4 import BeautifulSoup

from datetime import datetime
from xml.dom import minidom
from dotenv import load_dotenv

import xml.dom.minidom


class XliffManager:
    def __init__(self):
        self.logger = LoggerManager().get_logger()

    def parse_file(self, file, log_stats=False):

        try:
            if not os.path.exists(file):
                self.logger.error(f"File not found: {file}")
            else:
                tree = ET.parse(file)
                if log_stats:
                    file_name = os.path.basename(file)
                    self.logger.info(f"File {file_name} successfully parsed:")

                    trans_unit_count = len(tree.findall(".//trans-unit"))
                    self.logger.info(f"\t ->Trans-units Total: {trans_unit_count}")

                    target_count = len(tree.findall(".//target"))
                    self.logger.info(f"\t ->Trans-units with target: {target_count}")

            return tree

        except Exception as e:
            self.logger.error(f"Error reading the XLIFF file: {e}")
            return None

    def get_trans_unit_values(self, trans_unit):

        trans_id = trans_unit.get("id", "N/A")
        maxwidth = trans_unit.get("maxwidth", "N/A")
        size_unit = trans_unit.get("size-unit", "N/A")
        source = (
            trans_unit.find("source").text
            if trans_unit.find("source") is not None
            else "N/A"
        )
        target = (
            trans_unit.find("target").text
            if trans_unit.find("target") is not None
            else ""
        )
        note = (
            trans_unit.find("note").text
            if trans_unit.find("note") is not None
            else "N/A"
        )

        return trans_id, maxwidth, size_unit, source, target, note

    def get_only_trans_units_with_target(self, xml_tree):

        self.logger.info(f"\t ->Reading trans-units with <target> from the total <trans-unit>...")
        try:
            root = xml_tree.getroot()
            # Find all trans-unit elements that has a target element (i.e. has a translation)
            trans_units_nodes = ""
            for trans_unit in root.findall(".//trans-unit[target]"):

                trans_id, maxwidth, size_unit, source, target, note = (
                    self.get_trans_unit_values(trans_unit)
                )

                trans_units_nodes += f'<trans-unit id="{trans_id}" maxwidth="{maxwidth}" size-unit="{size_unit}"> <source>{source}</source> <target>{target}</target></trans-unit>'

            return trans_units_nodes

        except Exception as e:
            self.logger.error(f"Error parsing the contents: {e}")
            return []

    def create_translations_xlif_file(
        self,
        request_folder,
        target_xlf_file_path,
        target_xlf_file_baseline,
        target_iso_language,
    ):

        header = '<?xml version="1.0" encoding="UTF-8"?><xliff version="1.2"><file original="Salesforce" source-language="en_US" target-language="{lang}" translation-type="metadata" datatype="xml"><body>'
        footer = "</body></file></xliff>"

        header_lang = header.format(lang=target_iso_language)

        # Read all files ending with Response.xml and append their content to a variable
        content = ""
        file_pattern = os.path.join(request_folder, 'partial_files', "*-Response.txt")
        files = sorted(glob.glob(file_pattern))

        for partial_file in files:
            try:
                with open(partial_file, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    content += file_content
            except IOError as e:
                self.logger.error(f"Error reading {partial_file}: {e}")

        full_xml = header_lang + content + footer

        # Write the full XML content to the target file
        with open(target_xlf_file_path, "w", encoding="utf-8") as f:
            f.write(full_xml)

        self.logger.info(f"XLF created: {target_xlf_file_path}")
        
        target_file_cleaned = self.xlf_cleanup_file(target_xlf_file_path)

        return target_file_cleaned

    def clean_inner(self, text):
        # Cleaning the source and the target strings
        # Temporarily replace tags to avoid encoding them
        text = text.replace("<source>", "TAG_SOURCE")
        text = text.replace("</source>", "TAG_END_SOURCE")
        text = text.replace("<target>", "TAG_TARGET")
        text = text.replace("</target>", "TAG_END_TARGET")

        # Replace special characters with their XML-safe equivalents
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("•", "&#8226;")
        # The tab character was present in the id="CustomLabel.dfsle__DecMergeFieldsGuidanceStep3ImageInformation3" maxwidth="1000"> <source>&#8226;	&lt
        text = text.replace("\t", "   ")  # Tab character makes the import to fail
        text = text.replace("\n", "&#10;")
        text = text.replace("\r", "&#13;")

        # Restore the original tags
        text = text.replace("TAG_SOURCE", "<source>")
        text = text.replace("TAG_END_SOURCE", "</source>")
        text = text.replace("TAG_TARGET", "<target>")
        text = text.replace("TAG_END_TARGET", "</target>")

        return text

    def clean_opening(self, text):
        original_id_value = text.group(1)
        cleaned_value = (
            original_id_value.replace("&", "").replace("<", "").replace(">", "")
        )

        return f'id="{cleaned_value}"'

    def clean_reduce(self, input_file, output_file):

        with open(input_file, "r", encoding="utf-8", errors="replace") as f:
            file_text = f.read()

        # Regex to capture the entire <trans-unit> block:
        #   1) Opening tag (including attributes) -> group(1)
        #   2) The inner content (including <source>, <target> etc.) -> group(2)
        #   3) The closing </trans-unit> tag -> group(3)
        trans_unit_pattern = re.compile(r"(<trans-unit[^>]*>)(.*?)(</trans-unit>)", flags=re.DOTALL | re.IGNORECASE)

        # Function to process each match (one <trans-unit> block):
        def process_trans_unit(match):

            # e.g. <trans-unit id="..." maxwidth="240" size-unit="char">
            opening_tag = match.group(1)
            # e.g. <source>...</source><target>...</target><note>...</note>
            inner_content = match.group(2)
            # e.g. </trans-unit>
            closing_tag = match.group(3)

            # Regex to capture the value inside id="...."
            pattern = re.compile(r'id="([^"]*)"')
            opening_tag = pattern.sub(self.clean_opening, opening_tag)

            inner_content = self.clean_inner(inner_content)

            # 1. Extract maxwidth from the opening tag and look for maxwidth="..."
            width_match = re.search(
                r'maxwidth\s*=\s*"(\d+)"', opening_tag, flags=re.IGNORECASE
            )
            if width_match:
                maxwidth = int(width_match.group(1))

            # 2. Find <target>...</target> in the inner content
            #    We'll capture the entire <target> text so we can do a replacement
            target_pattern = re.compile(
                r"(<target\s*>)(.*?)(</target\s*>)", flags=re.DOTALL | re.IGNORECASE
            )
            target_match = target_pattern.search(inner_content)

            if target_match:
                target_open_tag = target_match.group(1)  # <target>
                # The text inside <target>...</target>
                target_text = target_match.group(2)
                target_close_tag = target_match.group(3)  # </target>

                # 3. Truncate target text if longer than maxwidth
                if len(target_text) > maxwidth:
                    self.logger.info(f"{target_text}--TOO LONG width: {maxwidth} -- id = {opening_tag}")
                    
                    # Remove the last word completely and add ...
                    target_text = re.sub(r'\s+\S+$', ' ...', target_text[:maxwidth])

                # 4. Rebuild the <target> with truncated text
                new_target = f"{target_open_tag}{target_text}{target_close_tag}"

                # 5. Replace old <target> section in inner_content
                start, end = target_match.span()
                inner_content = inner_content[:start] + new_target + inner_content[end:]

            # 6. Rebuild entire trans-unit block
            new_block = f"{opening_tag}{inner_content}{closing_tag}"
            return new_block

        # Use re.sub with a function to replace each <trans-unit> block
        new_text = trans_unit_pattern.sub(process_trans_unit, file_text)

        # Write the updated text to output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(new_text)

        print(f"Truncated targets to maxwidth: {output_file} saved.")

    def xlf_cleanup_file(self, input_file):

        cleaned_file_name = input_file + "-truncated-cleaned.xlf"
        self.clean_reduce(input_file, cleaned_file_name)

        return cleaned_file_name
    
    def compare_xlif_files(self, source_xlf_file, dest_xlf_file, excluded_literals, exclusion_patterns):
        
        trans_units_in_source_not_in_dest = []
        try:
            # Parse the source and destination XML files
            source_tree = ET.parse(source_xlf_file) 
            destination_tree = ET.parse(dest_xlf_file)

            source_root = source_tree.getroot()
            destination_root = destination_tree.getroot()

            # Create a set of trans-unit ids in the source file which has targete
            source_trans_unit_ids = set()
            for trans_unit in source_root.findall(".//trans-unit"):
                target = trans_unit.find("target")
                if target is not None:
                    trans_id = trans_unit.get("id")
                    source_trans_unit_ids.add(trans_id)

            # Create a set of trans-unit ids in the destination file
            destination_trans_unit_ids = set()
            for trans_unit in destination_root.findall(".//trans-unit"):
                trans_id = trans_unit.get("id")
                if trans_id:
                    destination_trans_unit_ids.add(trans_id)

            for trans_unit_id in source_trans_unit_ids:
                # Check if the trans_unit_id starts with any of the excluded patterns
                if exclusion_patterns is not None:
                    if any(trans_unit_id.startswith(pattern) for pattern in exclusion_patterns):
                        # This trans_unit is excluded, do nothing
                        continue 
                
                elif (excluded_literals is not None) and (trans_unit_id in excluded_literals):
                    # This trans_unit is excluded, do nothing
                    continue
                
                elif trans_unit_id not in destination_trans_unit_ids:
                    #self.logger.info(f"Missing trans-unit in target file: {trans_unit_id}")
                    trans_units_in_source_not_in_dest.append(trans_unit)
        
            return trans_units_in_source_not_in_dest

        except Exception as e:
            self.logger.error(f"Error processing the XML files: {e}")
            return []
    
        