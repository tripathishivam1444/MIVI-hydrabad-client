import streamlit as st
import pytesseract
from PIL import Image, ImageEnhance
import re
import os
import tempfile
import glob
from PIL.ExifTags import TAGS

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

def correct_image_orientation(image):
    """Correct image orientation based on EXIF metadata."""
    try:
        exif = image.getexif()
        if exif is not None:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'Orientation':
                    if value == 3:
                        image = image.rotate(180, expand=True)
                    elif value == 6:
                        image = image.rotate(-90, expand=True)
                    elif value == 8:
                        image = image.rotate(90, expand=True)
                    break
    except Exception:
        pass
    # Heuristic: Rotate if width > height (common for mobile images)
    if image.width > image.height:
        image = image.rotate(-90, expand=True)
    return image

def reset_captured_images():
    """Reset captured images and extracted text."""
    for image_path in st.session_state.captured_images:
        try:
            os.remove(image_path)
        except:
            pass
    st.session_state.captured_images = []
    st.session_state.extracted_texts = []
    st.session_state.matching_numbers = None

def switch_screen(screen_name):
    """Switch to a different screen."""
    st.session_state.current_screen = screen_name

def extract_invoice_numbers(text):
    """Extract 13-digit invoice numbers, handling potential OCR noise."""
    # Clean text: remove spaces, dashes, commas within numbers
    cleaned_text = re.sub(r'[\s,-]', '', text)
    # Match exactly 13 digits
    pattern = r'\b\d{13}\b'
    numbers = re.findall(pattern, cleaned_text)
    # Debug: Print extracted numbers
    print(f"Extracted numbers: {numbers}")
    return numbers

def compare_invoice_numbers(text1, text2):
    """Compare invoice numbers between two texts and find matches."""
    numbers1 = extract_invoice_numbers(text1)
    numbers2 = extract_invoice_numbers(text2)
    matches = [num for num in numbers1 if num in numbers2]
    return matches if matches else None

def process_images():
    """Process uploaded images with OCR and compare them."""
    try:
        with st.spinner('Processing images...'):
            extracted_texts = []
            for image_path in st.session_state.captured_images:
                # Open image and correct orientation
                image = Image.open(image_path)
                image = correct_image_orientation(image)
                
                # Preprocess image for better OCR
                image = image.convert('L')  # Convert to grayscale
                image = ImageEnhance.Contrast(image).enhance(2.0)  # Increase contrast
                image = image.resize((int(image.width * 1.5), int(image.height * 1.5)))  # Increase resolution
                
                # Perform OCR with specific config for digits
                text = pytesseract.image_to_string(image, lang='eng', config='--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789')
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
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("BACK", use_container_width=True):
            switch_screen('home')
    
    with col2:
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
    
    # Display images side by side
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Document 1")
        if st.session_state.captured_images:
            image = Image.open(st.session_state.captured_images[0])
            image = correct_image_orientation(image)
            st.image(image, use_column_width=True)
    
    with col2:
        st.subheader("Document 2")
        if len(st.session_state.captured_images) > 1:
            image = Image.open(st.session_state.captured_images[1])
            image = correct_image_orientation(image)
            st.image(image, use_column_width=True)
    
    # Match status
    if st.session_state.matching_numbers:
        st.markdown('<p style="color:green;font-size:20px;">✅ MATCHED!</p>', unsafe_allow_html=True)
        st.write(f"Invoice Number: {st.session_state.matching_numbers[0]}")
    else:
        st.markdown('<p style="color:red;font-size:20px;">❌ NO MATCH FOUND</p>', unsafe_allow_html=True)
        st.write("No matching invoice numbers between documents")
    
    # Display extracted text side by side
    text_col1, text_col2 = st.columns(2)
    
    with text_col1:
        st.subheader("Document 1 Text:")
        if st.session_state.extracted_texts:
            st.text_area("", value=st.session_state.extracted_texts[0], height=300)
    
    with text_col2:
        st.subheader("Document 2 Text:")
        if len(st.session_state.extracted_texts) > 1:
            st.text_area("", value=st.session_state.extracted_texts[1], height=300)
    
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
