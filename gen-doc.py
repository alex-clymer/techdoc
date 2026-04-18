import os
import re
import yaml
import markdown
import argparse
import subprocess
import shutil
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

# Define alert icons svg path
tip_icon = '''<svg aria-hidden="true" class="icon-svg" viewBox="0 0 16 16" version="1.1" width="16" height="16"><path d="M8 1.5c-2.363 0-4 1.69-4 3.75 0 .984.424 1.625.984 2.304l.214.253c.223.264.47.556.673.848.284.411.537.896.621 1.49a.75.75 0 0 1-1.484.211c-.04-.282-.163-.547-.37-.847a8.456 8.456 0 0 0-.542-.68c-.084-.1-.173-.205-.268-.32C3.201 7.75 2.5 6.766 2.5 5.25 2.5 2.31 4.863 0 8 0s5.5 2.31 5.5 5.25c0 1.516-.701 2.5-1.328 3.259-.095.115-.184.22-.268.319-.207.245-.383.453-.541.681-.208.3-.33.565-.37.847a.751.751 0 0 1-1.485-.212c.084-.593.337-1.078.621-1.489.203-.292.45-.584.673-.848.075-.088.147-.173.213-.253.561-.679.985-1.32.985-2.304 0-2.06-1.637-3.75-4-3.75ZM5.75 12h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5ZM6 15.25a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5a.75.75 0 0 1-.75-.75Z"/></svg>'''
note_icon = '''<svg aria-hidden="true" class="icon-svg" viewBox="0 0 16 16" version="1.1" width="16" height="16"><path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></svg>'''
important_icon = '''<svg aria-hidden="true" class="icon-svg" viewBox="0 0 16 16" version="1.1" width="16" height="16"><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v9.5A1.75 1.75 0 0 1 14.25 13H8.06l-2.573 2.573A1.458 1.458 0 0 1 3 14.543V13H1.75A1.75 1.75 0 0 1 0 11.25Zm1.75-.25a.25.25 0 0 0-.25.25v9.5c0 .138.112.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h6.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25Zm7 2.25v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/></svg>'''
video_icon = '''<svg class="icon-svg" xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#1f1f1f"><path d="m380-300 280-180-280-180v360ZM480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/></svg>'''

# Define icon paths and alert class mapping for different alert types
ALERT_TYPE_MAPPING = {
    '[!TIP]': ('alert-tip', 'alert-title alert-title-tip', 'Tip:', tip_icon),
    '[!IMPORTANT]': ('alert-important', 'alert-title alert-title-important',  'Important:', important_icon),
    '[!NOTE]': ('alert-note', 'alert-title alert-title-note',  'Note:', note_icon),
    '[!VIDEO]': ('alert-video', 'alert-title alert-title-video',  'Watch a tutorial', video_icon),
}

def collect_md_files_in_order(nav_structure, base_path):
    """
    Return absolute markdown file paths in the exact order from nav.yml.
    """
    ordered = []
    for section in nav_structure:
        for _, files in section.items():
            for md_file in files:
                ordered.append(str(Path(base_path) / md_file))
    return ordered

# Parse the nav.yml file to get the navigation structure.
def parse_nav_yaml(nav_file):
    with open(nav_file, 'r', encoding='utf-8') as file:
        nav = yaml.safe_load(file)
    return nav.get('site_name', 'Documentation'), nav['nav']

# Convert links from .md to .html
def update_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    # Regex to match .md at the end of the href or before an anchor (#...)
    md_link_regex = re.compile(r'\.md($|#)')
    for link in soup.find_all('a', href=md_link_regex):
        # Replace ".md" with ".html", preserving any anchor
        link['href'] = re.sub(r'\.md($|#)', r'.html\1', link['href'])
    return str(soup)

# Add ids to headings to maintain linking
def add_ids(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    # Add the id attribute
    for heading in soup.find_all(('h2', 'h3', 'h4')):
        # Extract the text, convert to lowercase, replace spaces with hyphens, and remove special characters
        heading_id = re.sub(r'[^\w\s-]', '', heading.text.strip()).replace(' ', '-').lower()
        heading['id'] = heading_id
    return str(soup)

# Remove / that's causing images not to be found
def process_images(html_content):
    """Fix image paths in the provided HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all <img> tags in the HTML
    for img_tag in soup.find_all('img'):
        if 'src' in img_tag.attrs:
            # Remove the leading '/' from the 'src' attribute if it exists
            img_tag['src'] = img_tag['src'].lstrip('/')

    # Return the updated HTML content
    return str(soup)

def convert_alerts(html_content):
    """Convert blockquote with [!TYPE] into a styled alert div dynamically."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all <blockquote> elements in the HTML
    for blockquote in soup.find_all('blockquote'):
        p_tag = blockquote.find('p')
        if p_tag:
            # Check for any defined alert types in the blockquote
            for alert_marker, (alert_class, alert_title, alert_label, svg_icon) in ALERT_TYPE_MAPPING.items():
                if alert_marker in p_tag.get_text():
                    # Extract the content of the blockquote
                    content = p_tag.encode_contents().decode('utf-8').replace(alert_marker, '').strip()

                    # Parse the content and separate the first line (title) and the rest
                    content_soup = BeautifulSoup(content, 'html.parser')
                    em_tag = content_soup.find('em')  # Find the <em> tag for the first line
                    em_text = em_tag.get_text() if em_tag else ""  # Extract the text from <em>
                    if em_tag:
                        em_tag.extract()  # Remove the <em> tag from content so we only have the remaining content

                    # The remaining content after the <em> tag
                    remaining_content = content_soup.decode_contents().strip()

                    # Create the new <div> structure
                    alert_div = soup.new_tag('div', **{'class': f'alert {alert_class}'})

                    # Create the alert title with the SVG icon and dynamic <em> text
                    alert_title = soup.new_tag('p', **{'class': alert_title})
                    svg_icon_soup = BeautifulSoup(svg_icon, 'html.parser')  # Parse the SVG icon
                    alert_title.append(svg_icon_soup)  # Add the SVG icon to the alert title

                    # Add the alert label (like "Tip:", "Important:", "Note:") and the extracted <em> text
                    alert_title.append(f" {alert_label} ")
                    if em_text:
                        em_tag = soup.new_tag('em')
                        em_tag.string = em_text
                        alert_title.append(em_tag)

                    # Add the alert title to the alert div
                    alert_div.append(alert_title)

                    # Create the second paragraph with the remaining content
                    if remaining_content:
                        remaining_paragraph = soup.new_tag('p')
                        remaining_paragraph.append(BeautifulSoup(remaining_content, 'html.parser'))
                        alert_div.append(remaining_paragraph)

                    # Replace the blockquote with the new alert div
                    blockquote.replace_with(alert_div)
                    break  # Exit the loop once a match is found

    # Return the modified HTML
    return str(soup)

def extract_headings_from_md(file_path):
    """
    Extract headings (H1 through H2) from a markdown file.
    - H1 (#) headings will not have slugs, as they represent the top-level of the page.
    - H2 (##) and lower headings will generate slugs for navigation.

    :param file_path: Path to the markdown file.
    :return: List of tuples (level, text, slug). Slug will be None for H1.
    """
    headings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                # Match markdown headings (e.g., #, ##, ###, etc.)
                match = re.match(r'^(#{1,2})\s+(.*)', line)  # Allow up to 6 heading levels
                if match:
                    level = len(match.group(1))  # Number of '#' indicates the heading level
                    text = match.group(2).strip()  # Heading text

                    # For H1 headings, slug is None as it's the top-level of the page
                    slug = None if level == 1 else re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-').strip('-')

                    # Add the heading to the list
                    headings.append((level, text, slug))
    except FileNotFoundError:
        print(f"Warning: File not found - {file_path}")
    return headings


def append_headings_to_ul(headings, parent_ul, nav, file_name):
    """Recursively append headings to the appropriate nested UL, with a <div> wrapping <li> elements in sub-menus."""
    current_level = 1
    current_ul = parent_ul
    current_li = None

    for level, text, slug in headings:
        while level > current_level:
            # Create a nested <ul> for deeper levels
            nested_ul = nav.new_tag('ul', **{'class': 'sub-menu'})

            # Create a <div> to wrap the <li> elements in the sub-menu
            li_wrapper_div = nav.new_tag('div')  # Wrapper <div> for <li> elements
            nested_ul.append(li_wrapper_div)    # Append the <div> to the nested <ul>

            if current_li:  # Ensure the <ul> is nested inside the current <li>
                current_li.append(nested_ul)
            current_ul = li_wrapper_div  # Set current_ul to the wrapper <div>
            current_level += 1

        while level < current_level:
            # Move back up to the parent level
            current_ul = current_ul.find_parent('ul')
            current_level -= 1

        # Add the heading as a <li> with a link
        li = nav.new_tag('li', **{'class': f'h{level}'})

        # Create the link
        if slug is None:
            # For top-level headings (H1) without a slug, use the file name as the href
            a = nav.new_tag('a', href=file_name)
        else:
            # For other headings, include the slug in the href
            a = nav.new_tag('a', href=f"{file_name}#{slug}")

        # Add the heading text within a <span>
        span = nav.new_tag('span')
        span.string = text
        a.append(span)

        if level == 1:  # Only add the <div> wrapper and button for top-level links
            # Create the dropdown button for top-level items
            button = nav.new_tag('button', type='button', **{'class': 'dropdown-btn'})
            svg = nav.new_tag('svg', xmlns="http://www.w3.org/2000/svg", height="24px", width="24px", fill="#1f1f1f", viewBox="0 -960 960 960")
            path = nav.new_tag('path', d="M504-480 320-664l56-56 240 240-240 240-56-56 184-184Z")
            svg.append(path)
            button.append(svg)

            # Wrap the button and link in a <div> with onclick
            wrapper_div = nav.new_tag('div', **{
                'class': f'h{level}-wrapper',
                'onclick': 'toggleSubMenu(this)'
            })
            wrapper_div.append(button)  # Add the button to the wrapper
            wrapper_div.append(a)      # Add the link to the wrapper

            # Append the <div> to the <li>
            li.append(wrapper_div)
        else:
            # For lower-level links, just append the link directly to the <li>
            li.append(a)

        # Append the <li> to the current <div> (wrapper for sub-menu <li>)
        current_ul.append(li)

        # Update the current <li> for nesting submenus if needed
        current_li = li
        
def generate_html_nav(nav_structure, base_path):
    """
    Generate the HTML navigation based on the nav structure and headings.

    :param nav_structure: A list of sections with titles and associated files.
    :param base_path: The base path to locate the markdown files.
    :return: A string representing the HTML navigation.
    """
    # Create the base navigation structure
    nav = BeautifulSoup('<nav id="sidebar"><ul></ul></nav>', 'html.parser')
    ul = nav.find('ul')  # Start with the main <ul>

    is_first_section = True  # Flag to track the first section

    for section in nav_structure:
        for section_title, files in section.items():
            # Determine if we are handling the first section or subsequent ones
            if is_first_section:
                # Handle the first section with a custom home icon
                for file in files:
                    ul.append(create_home_section(nav, section_title, file, base_path))
                is_first_section = False  # Mark the first section as processed
            else:
                # Handle all other sections
                ul.append(create_section(nav, section_title, files, base_path))

    return nav.prettify()


def create_home_section(nav, section_title, file, base_path):
    """
    Create the first section (home section) with a custom SVG icon.

    :param nav: A BeautifulSoup object for creating HTML.
    :param section_title: The title of the first section.
    :param file: The file associated with the first section.
    :param base_path: The base path to locate the file.
    :return: A BeautifulSoup <li> representing the first section.
    """
    file_only = os.path.splitext(file)[0]
    file_name = file_only + ".html"

    # Create the top-level <li> for the first section
    section_li = nav.new_tag('li', **{'class': 'section', 'id': file_only})

    # Wrapper div for the home section
    div = nav.new_tag('div', **{'class': 'home-wrapper'})  # No rotate class

    # Create the <a> tag as the link to the file
    a = nav.new_tag('a', href=file_name)
    a.string = section_title  # Match the title from the YAML file

    # Create the button and add the custom SVG icon
    button = nav.new_tag('button', type='button', **{'class': 'icon-btn'})

    # Add the custom SVG icon inside the button
    svg = nav.new_tag('svg', xmlns="http://www.w3.org/2000/svg", height="24px", width="24px", fill="#1f1f1f", viewBox="0 -960 960 960")
    path = nav.new_tag('path', d="M240-200h120v-240h240v240h120v-360L480-740 240-560v360Zm-80 80v-480l320-240 320 240v480H520v-240h-80v240H160Zm320-350Z")
    svg.append(path)
    button.append(svg)  # Append the SVG icon to the button

    # Add the <a> and <button> as siblings in the wrapper
    div.append(button)  # Append the button
    div.append(a)  # Append the link

    # Add the div to the section <li>
    section_li.append(div)

    return section_li


def create_section(nav, section_title, files, base_path):
    """
    Create a standard section (non-home) with nested headings and links.

    :param nav: A BeautifulSoup object for creating HTML.
    :param section_title: The title of the section.
    :param files: A list of files in the section.
    :param base_path: The base path to locate the files.
    :return: A BeautifulSoup <li> representing the section.
    """
    file_only = os.path.splitext(files[0])[0]
    file_name = file_only + ".html"

    # Create the top-level <li> for the section
    section_li = nav.new_tag('li', **{'class': 'section', 'id': file_only})

    # Create the section link
    a = nav.new_tag('a', href=f'{file_name}#top')
    a.string = section_title  # Match the title from the YAML file without transforming to uppercase

    # Wrap the <a> tag in a menu-wrapper <div> (no dropdown button)
    div = nav.new_tag('div', **{'class': 'section-wrapper'})
    div.append(a)

    # Append the menu-wrapper <div> to the top-level <li>
    section_li.append(div)

    # Create the section-menu <ul>
    section_ul = nav.new_tag('ul', **{'class': 'section-menu'})
    section_li.append(section_ul)

    # Process each file in the section
    for file in files:
        file_path = os.path.join(base_path, file)
        file_name = os.path.splitext(file)[0] + ".html"

        if os.path.exists(file_path):
            headings = extract_headings_from_md(file_path)  # Extract headings from the file
            if headings:
                append_headings_to_ul(headings, section_ul, nav, file_name)

    return section_li

def highlight_active_page(nav_html, current_file):
    """
    Updates the navigation HTML to:
    - Add an 'active' and 'rotate' class to the top-level wrapper for the current file
    - Add 'show' class to sub-menu for active file
    """
    soup = BeautifulSoup(nav_html, 'html.parser')
    try:
        current_href = soup.find('a', href=f'{current_file}')
        parent_div = current_href.parent

        if current_file == 'index.html':
            parent_div['class'].append('active')
        else:
            parent_div['class'].extend(['active', 'rotate'])
            sub_menu = parent_div.find_next_sibling('ul')
            sub_menu['class'].append('show')
            
    except Exception:
        print(f'Unable to process active page for {current_file}')

    return str(soup)

def render_template(template_name, content):
    try:
        # Set up Jinja2 environment
        env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Load the template
        template = env.get_template(template_name)

        return template.render(content)
    except Exception as e:
        raise RuntimeError(f"Error rendering template: {e}") from e

def generate_html_from_md(md_file, html_nav, title="Documentation"):
    """Convert a Markdown file to HTML and save it to the output directory."""
    try:
        # Derive the HTML file name for the current Markdown file
        current_file = os.path.splitext(os.path.basename(md_file))[0] + '.html'

        # Highlight the active page in the navigation
        updated_html_nav = highlight_active_page(html_nav, current_file)

        # Read the content of the Markdown file
        with open(md_file, 'r', encoding='utf-8') as file:
            md_content = file.read()

        # Convert Markdown to HTML (use the markdown library)
        html_main = markdown.markdown(md_content)

        # Add IDs to headings (if applicable)
        html_main = add_ids(html_main)

        # Update links from .md to .html
        html_main = update_links(html_main)

        # Fix image path issue
        html_main = process_images(html_main)

        # Create notes, tips, alerts
        html_main = convert_alerts(html_main)

        # Structure the content for the template
        html_content = {
            "nav": updated_html_nav,  # Use the updated navigation with the active class
            "content": {
                "title": title,
                "main": html_main,
            }
        }

        # Render the HTML using the template
        output_html = render_template('user-doc-template.html', html_content)

        # Save the HTML output
        output_file = os.path.splitext(os.path.basename(md_file))[0] + '.html'
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(output_html)

        print(f"Generated HTML: {output_file}")
    except Exception as e:
        print(f"Error generating HTML for {md_file}: {e}")

def generate_single_pdf_with_pandoc(md_files, output_pdf, title="Documentation", css_file=None, toc=False, toc_depth=3):
    """
    Generates a single PDF using Pandoc from a list of Markdown files.
    """
    if not shutil.which("pandoc"):
        raise RuntimeError("Pandoc is not installed or not on PATH.")

    # CHANGE: added --pdf-engine=weasyprint (requires: brew install weasyprint)
    cmd = [
        "pandoc",
        *md_files,
        "-o", output_pdf,
        "--pdf-engine=weasyprint",
        "--metadata", f"title={title}"
    ]

    # CHANGE: added optional --css flag (pass via --pdf-css on the command line)
    if css_file:
        cmd += ["--css", css_file]

    # CHANGE: added optional TOC flags (pass via --pdf-toc and --pdf-toc-depth on the command line)
    if toc:
        cmd += ["--toc", f"--toc-depth={toc_depth}"]

    subprocess.run(cmd, check=True)
    print(f"✓ PDF generated: {output_pdf}")

def main():
    
    # ----------------------
    # Argument parser (new)
    # ----------------------
    parser = argparse.ArgumentParser(description="Generate HTML and optional PDF from Markdown.")
    parser.add_argument("--pdf", action="store_true", help="Generate a single merged PDF using Pandoc.")
    parser.add_argument("--pdf-output", default="docs.pdf", help="Output PDF filename.")
    parser.add_argument("--pdf-css", default=None, help="Path to a CSS file to style the PDF.")
    parser.add_argument("--pdf-toc", action="store_true", help="Include a table of contents in the PDF.")
    parser.add_argument("--pdf-toc-depth", type=int, default=3, help="Depth of headings in the PDF table of contents (default: 3).")
    args = parser.parse_args()


    # Paths
    nav_file = 'markdown/nav.yml'  # Path to your nav.yml file
    base_path = 'markdown'  # Directory where markdown files are stored
    template_dir = 'templates'  # Directory where Jinja2 templates are stored

    # Parse the nav.yml file
    site_title, nav_structure = parse_nav_yaml(nav_file)

    # Generate the navigation HTML
    nav_html = generate_html_nav(nav_structure, base_path)

    # Process each Markdown file in the navigation structure
    for section in nav_structure:
        for _, files in section.items():
            for md_file in files:
                # Full path to the Markdown file
                md_file_path = os.path.join(base_path, md_file)

                # Check if the Markdown file exists
                if os.path.exists(md_file_path):
                    # Generate HTML for the Markdown file
                    generate_html_from_md(md_file_path, nav_html, title=site_title)
                else:
                    print(f"Warning: Markdown file not found - {md_file_path}")

    print("HTML generation completed.")

    if args.pdf:
        md_files = collect_md_files_in_order(nav_structure, base_path)
        generate_single_pdf_with_pandoc(md_files, args.pdf_output, title=site_title, css_file=args.pdf_css, toc=args.pdf_toc, toc_depth=args.pdf_toc_depth)


if __name__ == '__main__':
    main()