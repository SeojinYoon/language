#!/usr/bin/env python3
"""
build_data.py
Parses English/dissimilarities.md and English/Words_organized.md
and exports them into vocab_app/data.js for offline and double-click (file://) support.
"""

import os
import re
import json
import sys

def parse_dissimilarities(text):
    lines = text.split('\n')
    item_list = []
    current_category = ''
    current_item = None
    id_counter = 1

    for raw_line in lines:
        line = raw_line.rstrip('\r')
        trimmed = line.strip()
        if not trimmed:
            continue

        # Category: Level 1 bullet without colon, e.g. "- 보다", "- 제외"
        if re.match(r'^- [^:]+$', line):
            current_category = line[2:].strip()
            continue

        # Word: Indented bullet with colon, e.g. "    - see: (눈에 띄어 자연스럽게) 보다"
        word_match = re.match(r'^(\s{2,8}|\t)- (.+?):\s*(.*)$', line)
        if word_match:
            if current_item:
                item_list.append(current_item)
            current_item = {
                'id': f'd_{id_counter}',
                'source': 'Dissimilarities',
                'category': current_category or '기타',
                'word': word_match.group(2).replace('**', '').strip(),
                'meaning': word_match.group(3).strip(),
                'core_image': '',
                'focus': '',
                'examples': []
            }
            id_counter += 1
            continue

        if not current_item:
            continue

        # Core image
        core_match = re.match(r'^\*\s*코어 이미지:\s*(.*)$', trimmed)
        if core_match:
            current_item['core_image'] = core_match.group(1).strip()
            continue

        # Focus
        focus_match = re.match(r'^\*\s*초점:\s*(.*)$', trimmed)
        if focus_match:
            current_item['focus'] = focus_match.group(1).strip()
            continue

        # Examples
        ex_match = re.match(r'^>\s*(.*)$', trimmed)
        if ex_match:
            current_item['examples'].append(ex_match.group(1).strip())
            continue

    if current_item:
        item_list.append(current_item)
    return item_list

def parse_words_organized(text, start_id=1):
    lines = text.split('\n')
    item_list = []
    cat_stack = []
    current_item = None
    id_counter = start_id

    for raw_line in lines:
        line = raw_line.rstrip('\r')
        trimmed = line.strip()
        if not trimmed:
            continue

        indent_match = re.match(r'^(\s*)', line)
        indent = len(indent_match.group(1)) if indent_match else 0

        # Category heading: starts with - and does NOT have colon
        if trimmed.startswith('- ') and ':' not in trimmed:
            cat_name = re.sub(r'^[-*\s]+', '', trimmed)
            cat_name = re.sub(r'[*]+$', '', cat_name).strip()
            while cat_stack and cat_stack[-1]['indent'] >= indent:
                cat_stack.pop()
            cat_stack.append({'indent': indent, 'name': cat_name})
            continue

        # Word entry: starts with - and has a colon
        word_match = re.match(r'^- ([^:]+):\s*(.*)$', trimmed)
        if word_match:
            if current_item:
                item_list.append(current_item)
            while cat_stack and cat_stack[-1]['indent'] >= indent:
                cat_stack.pop()
            category = ' > '.join(c['name'] for c in cat_stack) or '기타'
            current_item = {
                'id': f'o_{id_counter}',
                'source': 'Words Organized',
                'category': category,
                'word': word_match.group(1).replace('**', '').strip(),
                'meaning': word_match.group(2).strip(),
                'core_image': '',
                'focus': '',
                'examples': []
            }
            id_counter += 1
            continue

        if not current_item:
            continue

        core_match = re.match(r'^\*\s*코어 이미지:\s*(.*)$', trimmed)
        if core_match:
            current_item['core_image'] = core_match.group(1).strip()
            continue

        focus_match = re.match(r'^\*\s*초점:\s*(.*)$', trimmed)
        if focus_match:
            current_item['focus'] = focus_match.group(1).strip()
            continue

        ex_match = re.match(r'^>\s*(.*)$', trimmed)
        if ex_match:
            current_item['examples'].append(ex_match.group(1).strip())
            continue

    if current_item:
        item_list.append(current_item)
    return item_list

def build(project_root=None, output_path=None):
    if project_root is None:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(curr_dir)

    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")

    dis_path = os.path.join(project_root, "English", "dissimilarities.md")
    org_path = os.path.join(project_root, "English", "Words_organized.md")

    if not os.path.exists(dis_path) or not os.path.exists(org_path):
        print(f"❌ Markdown files not found under {project_root}/English")
        return False

    with open(dis_path, 'r', encoding='utf-8') as f:
        dis_text = f.read()
    with open(org_path, 'r', encoding='utf-8') as f:
        org_text = f.read()

    dis_items = parse_dissimilarities(dis_text)
    org_items = parse_words_organized(org_text, start_id=len(dis_items) + 1)
    all_data = dis_items + org_items

    js_content = f"""/**
 * Auto-generated by build_data.py
 * Source: English/dissimilarities.md & English/Words_organized.md
 * Total words: {len(all_data)} (Dissimilarities: {len(dis_items)}, Words Organized: {len(org_items)})
 * Generated for 100% offline & double-click file:// support.
 */
window.VOCAB_DATA = {json.dumps(all_data, ensure_ascii=False, indent=2)};
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"✅ data.js built successfully: {len(all_data)} words ({len(dis_items)} Dissimilarities, {len(org_items)} Words Organized)")
    print(f"📁 Saved to: {output_path}")
    return True

if __name__ == '__main__':
    build()
