import streamlit as st
import pymupdf
import re
import google.generativeai as genai
import ebooklib
from ebooklib import epub
from io import BytesIO
import os
import tempfile
from bs4 import BeautifulSoup

default_prompt = """
# Mission

You are an expert teacher extracting key concepts/lessons and actionable frameworks/methodologies from educational video transcripts or book chapters. Your job is to provide a comprehensive, accurate and detailed summary of the content with a focus on practical application. This should replace needing to read the original content. 

# Rules

Please read through the text carefully. Your task is to extract a comprehensive, accurate and detailed summary of the content and to present them in a well-organized markdown format.

Look specifically for:
•⁠  ⁠Practical concepts and lessons 
•⁠  ⁠Specific anecdotes or stories that help explain a concept or lesson
•⁠  ⁠Specific actionable steps, how-tos or frameworks/methodologies

# Expected Input

You will receive the full text from the file.

<file_text>
{file_text}
</file_text>


# Output Format (in markdown)

1.⁠ ⁠Summary:
   - Provide a high-level executive summary of the content including the overall topics, purpose and outcomes expected

2.⁠ ⁠Topics:
   - List the key topics, concepts and/or lessons in concise bullet points including specific outcomes for the learner

3.⁠ ⁠Content
•⁠  ⁠provide a comprehensive, accurate and detailed summary of ALL content with a focus on practical application for the learner
•⁠  ⁠include all relevant detail from the content 
 - Outline specific anecdotes or stories that support key concepts or lessons

4.⁠ ⁠Action Items
 - Provide a comprehensive list of specific action items, how-to steps or frameworks for applying the knowledge within the content

Go over your output and ensure accuracy and perfection, it is very important that this is an A grade output suitable for educated individuals with limited time but need for detail/accuracy.

IMPORTANT!!! Output your response within <markdown></markdown> tags.

Example Format:

<markdown>

*Summary:*
Provide a high-level executive summary.

*Topics:*
•⁠  ⁠Topic/lesson 1
•⁠  ⁠Topic/lesson 2
•⁠  ⁠...

*Content:*
  - Concept, lesson, insight or topic in comprehensive detail including any related anecdotes/stories
  - ...

*Action items:*

  - Action Item 1: Step-by-step instructions
  - Action Item 2: Step-by-step instructions
  - …

</markdown>
"""

# Function to get key ideas using Google Gemini API
def get_key_ideas(file_text, api_key, prompt):
    print("Selected Text:")
    print(file_text)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    prompt = prompt.replace("{file_text}", file_text)
    try:
        response = model.generate_content(prompt)
        print(response)
        result = response.candidates[0].content.parts[0].text
        # Extract content between <markdown> tags using regex
        match = re.search(r'<markdown>(.*)', result, re.IGNORECASE | re.DOTALL)
        if match:
            key_ideas = match.group(1).strip()
            # Remove block quote formatting
            key_ideas = re.sub(r'^\s*>\s*', '', key_ideas, flags=re.MULTILINE)
        else:
            key_ideas = None
        
        return key_ideas
    except Exception as e:
        st.error(f"Error in Gemini API call: {str(e)}")
        return None

@st.cache_data
def process_file(file_content, file_type, start_page=None, end_page=None):
    try:
        if file_type == "application/pdf":
            # Process PDF file
            with BytesIO(file_content) as file:
                doc = pymupdf.open(stream=file, filetype="pdf")
                if start_page is not None and end_page is not None:
                    start_page = max(0, start_page - 1)
                    end_page = min(end_page, doc.page_count)
                    page_range = range(start_page, end_page)
                    full_text = "".join(doc[i].get_text() for i in page_range)
                else:
                    full_text = "".join(page.get_text() for page in doc)
                    
        elif file_type == "application/epub+zip":
            # Process epub file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            book = epub.read_epub(temp_file_path)
            full_text = ""

            for item in book.get_items():
                if isinstance(item, ebooklib.epub.EpubHtml):
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    full_text += soup.get_text()

            os.unlink(temp_file_path)  # Clean up the temporary file
        else:
            # Process txt file
            full_text = file_content.decode("utf-8")
        
        return full_text
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# Initialize session state variables
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

if 'uploaded_file_content' not in st.session_state:
    st.session_state['uploaded_file_content'] = None

if 'custom_prompt' not in st.session_state:
    st.session_state['custom_prompt'] = default_prompt

# Streamlit app
st.title("Lesson Extractor")

# Sidebar selection
page = st.sidebar.radio("Select Page", ("Home", "Prompt"))

if page == "Home":
    # Sidebar for file upload
    uploaded_file = st.sidebar.file_uploader("Upload a PDF, TXT, or EPUB file", type=["pdf", "txt", "epub"])
    if uploaded_file is not None:
        # Store the uploaded file content in session state
        st.session_state['uploaded_file_content'] = uploaded_file.read()
        st.session_state['file_type'] = uploaded_file.type

    # Sidebar for page interval selection
    if st.session_state.get('file_type') == "application/pdf":
        start_page = st.sidebar.text_input("Start Page", value="1")
        end_page = st.sidebar.text_input("End Page", value=str(pymupdf.open(stream=BytesIO(st.session_state['uploaded_file_content']), filetype="pdf").page_count))
    else:
        start_page = None
        end_page = None

    # Sidebar for API key input at the bottom
    st.session_state['api_key'] = st.sidebar.text_input("Enter your Google Gemini API key", value=st.session_state['api_key'])

    if st.session_state['uploaded_file_content']:
        # Display the selected text based on page intervals
        raw_text_placeholder = st.empty()

        if start_page and end_page:
            try:
                start_page = int(start_page)
                end_page = int(end_page)
                full_text = process_file(st.session_state['uploaded_file_content'], st.session_state['file_type'], start_page, end_page)
            except ValueError:
                st.warning("Invalid page numbers. Displaying the entire text.")
                full_text = process_file(st.session_state['uploaded_file_content'], st.session_state['file_type'])
        else:
            full_text = process_file(st.session_state['uploaded_file_content'], st.session_state['file_type'])

        raw_text_placeholder.write(full_text)
        
        # Extract button
        if st.sidebar.button("Extract Lessons"):
            # Clear the raw text and show extracting message
            raw_text_placeholder.empty()
            extracting_message = st.warning("Extracting key lessons...")

            # Get key ideas from the selected text
            if start_page and end_page:
                try:
                    start_page = int(start_page)
                    end_page = int(end_page)
                    selected_text = process_file(st.session_state['uploaded_file_content'], st.session_state['file_type'], start_page, end_page)
                    key_ideas = get_key_ideas(selected_text, st.session_state['api_key'], st.session_state['custom_prompt'])
                except ValueError:
                    st.warning("Invalid page numbers. Extracting lessons from the entire text.")
                    key_ideas = get_key_ideas(full_text, st.session_state['api_key'], st.session_state['custom_prompt'])
            else:
                key_ideas = get_key_ideas(full_text, st.session_state['api_key'], st.session_state['custom_prompt'])

            # Show success message and display key ideas
            extracting_message.empty()
            if key_ideas is None:
                st.error("Could not extract the lessons.")
            else:
                st.success("Key lessons extracted!")
                st.markdown(key_ideas)
    else:
        st.write("Please upload a PDF, TXT, or EPUB file using the sidebar.")

elif page == "Prompt":
    st.markdown('<span style="color:yellow;">**WARNING:** You NEED to mention &lt;file_text&gt;&lt;/file_text&gt; and &lt;markdown&gt;&lt;/markdown&gt; tags in the prompt. Make sure to press Save to apply changes', unsafe_allow_html=True)
    prompt = st.text_area("Edit the prompt below:", value=st.session_state['custom_prompt'], height=400)
    
    if st.button("Save"):
        st.session_state['custom_prompt'] = prompt
        st.success("Prompt saved!")
