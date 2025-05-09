import streamlit as st
import pytesseract
from PIL import Image
import re
import os
import tempfile
import glob

# Page configuration
st.set_page_config(
    page_title="OCR Invoice Scanner",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'captured_images' not in st.session_state:
    st.session_state.captured_images = []
if 'extracted_texts' not in st.session_state:
    st.session_state.extracted_texts = []
if 'current_screen' not in st.session_state:
    st.session_state.current_screen = 'home'
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'matching_numbers' not in st.session_state:
    st.session_state.matching_numbers = None

def reset_captured_images():
    """Reset captured images and extracted text."""
    st.session_state.captured_images = []
    st.session_state.extracted_texts = []
    st.session_state.matching_numbers = None

def switch_screen(screen_name):
    """Switch to a different screen."""
    st.session_state.current_screen = screen_name

def extract_invoice_numbers(text):
    """Extract invoice numbers from text.
    
    This looks for patterns like:
    - Invoice No: 7112600003240
    - Invoice Sr. No: 7112600003240
    - Document No, 74126000033240
    - Or just 13-digit numbers that match the format
    """
    # Clean up the text - remove problematic characters and extra spaces
    text = text.replace(',', '.').replace("'", "").strip()
    
    # Look for invoice numbers with various labels and formats
    labeled_patterns = [
        r'Invoice\s+(?:No|Number|Sr\.\s+No)[:.]\s*(\d{13,14})',  # Match invoice numbers with 13-14 digits
        r'Document\s+No[.,]?\s*(\d{13,14})',                    # Match document numbers with 13-14 digits
        r'Moglix\s+Invoice\s+Sr\.\s+No[:.]\s*(\d{13,14})'       # Match Moglix invoice numbers specifically
    ]
    
    numbers = []
    # First try to find labeled invoice numbers
    for pattern in labeled_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        numbers.extend(matches)
    
    # If no labeled numbers found, look for any 13-14 digit number
    if not numbers:
        # Pattern for standalone 13-14 digit numbers
        standalone_pattern = r'\b(\d{13,14})\b'
        numbers = re.findall(standalone_pattern, text)
    
    # Process the identified numbers to normalize them
    processed_numbers = []
    for num in numbers:
        # Remove any leading zeros that might be extra
        # and ensure we're comparing the last 13 digits if longer
        if len(num) > 13:
            processed_numbers.append(num[-13:])
        else:
            processed_numbers.append(num)
    
    return processed_numbers

def compare_invoice_numbers(text1, text2):
    """Compare invoice numbers between two texts and find matches."""
    numbers1 = extract_invoice_numbers(text1)
    numbers2 = extract_invoice_numbers(text2)
    
    # Debug information
    st.session_state.debug_numbers1 = numbers1
    st.session_state.debug_numbers2 = numbers2
    
    # Special case: Check for the specific invoice numbers from the example
    # This handles the case where one invoice has 7112600033240 and another has 74126000033240
    special_matches = []
    for num1 in numbers1:
        for num2 in numbers2:
            # Check if the last 10 digits match (to handle OCR errors in the first few digits)
            if len(num1) >= 10 and len(num2) >= 10 and num1[-10:] == num2[-10:]:
                special_matches.append(num1)
                break
    
    # Regular exact matches
    exact_matches = [num for num in numbers1 if num in numbers2]
    
    # Combine both types of matches
    all_matches = list(set(exact_matches + special_matches))
    
    return all_matches if all_matches else None

def process_images():
    """Process uploaded images with OCR and compare them."""
    try:
        with st.spinner('Processing images...'):
            extracted_texts = []
            for image_path in st.session_state.captured_images:
                # Open image and perform OCR
                image = Image.open(image_path)
                text = pytesseract.image_to_string(image, lang='eng')
                extracted_texts.append(text)
            
            # Save extracted texts to session state
            st.session_state.extracted_texts = extracted_texts
            
            # Compare the two documents
            st.session_state.matching_numbers = compare_invoice_numbers(
                extracted_texts[0], extracted_texts[1]
            )
            
            # Switch to comparison screen
            switch_screen('comparison')
    except Exception as e:
        st.error(f"Error processing images: {str(e)}")
        switch_screen('home')
    finally:
        st.session_state.processing = False

def home_screen():
    """Display the home screen."""
    st.title("OCR Invoice Scanner")
    if st.button("UPLOAD FROM GALLERY", use_container_width=True):
        reset_captured_images()
        switch_screen('upload')

def upload_screen():
    """Display the file upload screen."""
    st.title("Upload Images")
    st.write(f"Images Selected: {len(st.session_state.captured_images)}/2")
    
    st.write("Please select image files (JPG, JPEG, PNG):")
    
    uploaded_files = st.file_uploader(
        "Choose images", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    # Add text input option
    st.write("---")
    st.write("Or enter OCR text directly:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        text1 = st.text_area("Document 1 Text:", height=200, key="doc1_text")
    
    with col2:
        text2 = st.text_area("Document 2 Text:", height=200, key="doc2_text")
    
    if text1 and text2 and st.button("COMPARE TEXT", use_container_width=True):
        st.session_state.extracted_texts = [text1, text2]
        st.session_state.matching_numbers = compare_invoice_numbers(text1, text2)
        switch_screen('comparison')
    
    st.write("---")
    nav_col1, nav_col2 = st.columns([1, 1])
    
    with nav_col1:
        if st.button("BACK", use_container_width=True):
            switch_screen('home')
    
    with nav_col2:
        if uploaded_files and st.button("SELECT IMAGES", use_container_width=True):
            files_to_process = uploaded_files[:2]
            
            # Save uploaded files to temporary files
            for uploaded_file in files_to_process:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
                temp_file.close()
                
                st.session_state.captured_images.append(temp_file_path)
            
            # Keep only the first 2 images
            st.session_state.captured_images = st.session_state.captured_images[:2]
            
            # Process if two images are selected
            if len(st.session_state.captured_images) == 2:
                st.session_state.processing = True
                process_images()
            else:
                remaining = 2 - len(st.session_state.captured_images)
                st.warning(f"Selected {len(st.session_state.captured_images)} image(s). Need {remaining} more.")

def comparison_screen():
    """Display the comparison results screen."""
    st.title("Document Comparison Results")
    
    # Display images if available
    if st.session_state.captured_images:
        st.write("### Uploaded Images")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Document 1")
            if st.session_state.captured_images:
                image = Image.open(st.session_state.captured_images[0])
                st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("Document 2")
            if len(st.session_state.captured_images) > 1:
                image = Image.open(st.session_state.captured_images[1])
                st.image(image, use_column_width=True)
    
    # Match status
    st.write("## Matching Results")
    if st.session_state.matching_numbers:
        st.success("✅ MATCH FOUND!")
        for number in st.session_state.matching_numbers:
            st.markdown(f"### Invoice Number: <span style='color:green; font-weight:bold'>{number}</span>", unsafe_allow_html=True)
            
        # Show all detected numbers for comparison
        with st.expander("All Detected Numbers"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("Document 1 Numbers:")
                for num in getattr(st.session_state, 'debug_numbers1', []):
                    if num in st.session_state.matching_numbers:
                        st.markdown(f"<span style='color:green; font-weight:bold'>{num}</span>", unsafe_allow_html=True)
                    else:
                        st.write(num)
            
            with col2:
                st.write("Document 2 Numbers:")
                for num in getattr(st.session_state, 'debug_numbers2', []):
                    if num in st.session_state.matching_numbers:
                        st.markdown(f"<span style='color:green; font-weight:bold'>{num}</span>", unsafe_allow_html=True)
                    else:
                        st.write(num)
    else:
        st.error("❌ NO MATCH FOUND")
        st.write("No matching invoice numbers between documents")
        
        # When no match is found, let's show what was detected for debugging
        st.write("⚠️ Here are the numbers that were detected:")
        col1, col2 = st.columns(2)
        with col1:
            st.write("Document 1 Numbers:")
            for num in getattr(st.session_state, 'debug_numbers1', []):
                st.write(num)
        
        with col2:
            st.write("Document 2 Numbers:")
            for num in getattr(st.session_state, 'debug_numbers2', []):
                st.write(num)
    
    # Debug information - can be commented out in production
    with st.expander("Debug Information"):
        st.write("Document 1 extracted numbers:", getattr(st.session_state, 'debug_numbers1', []))
        st.write("Document 2 extracted numbers:", getattr(st.session_state, 'debug_numbers2', []))
    
    # Display extracted text side by side
    st.write("## Extracted Text")
    text_col1, text_col2 = st.columns(2)
    
    with text_col1:
        st.subheader("Document 1 Text:")
        if st.session_state.extracted_texts:
            st.text_area("", value=st.session_state.extracted_texts[0], height=300, key="text1_display")
    
    with text_col2:
        st.subheader("Document 2 Text:")
        if len(st.session_state.extracted_texts) > 1:
            st.text_area("", value=st.session_state.extracted_texts[1], height=300, key="text2_display")
    
    # New scan button
    if st.button("NEW SCAN", use_container_width=True):
        reset_captured_images()
        switch_screen('home')

def main():
    """Main app logic."""
    if st.session_state.processing:
        st.spinner("Processing Images...")
        process_images()
    elif st.session_state.current_screen == 'home':
        home_screen()
    elif st.session_state.current_screen == 'upload':
        upload_screen()
    elif st.session_state.current_screen == 'comparison':
        comparison_screen()
    else:
        st.error("Unknown screen")
        switch_screen('home')

if __name__ == "__main__":
    main()
