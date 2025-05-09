import streamlit as st
import easyocr
import cv2
import numpy as np
import re
import os
import glob
import tempfile
from PIL import Image as PILImage
import time

# Page configuration
st.set_page_config(
    page_title="OCR Invoice Scanner",
    page_icon="📄",
    layout="wide"
)

# Initialize session state if not already done
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

def delete_jpg_images():
    """Delete all temporary .jpg files."""
    jpg_files = glob.glob("*.jpg")
    
    for file in jpg_files:
        try:
            os.remove(file)
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Error deleting {file}: {e}")

def reset_captured_images():
    """Reset the captured images and extracted text."""
    st.session_state.captured_images = []
    st.session_state.extracted_texts = []
    st.session_state.matching_numbers = None

def switch_screen(screen_name):
    """Switch to a different screen."""
    st.session_state.current_screen = screen_name

def extract_invoice_numbers(text):
    """Extract invoice numbers (sequences of 11 or more digits) from text."""
    pattern = r'\b\d{11,}\b'
    return re.findall(pattern, text)

def compare_invoice_numbers(text1, text2):
    """Compare invoice numbers between two texts and find matches."""
    numbers1 = extract_invoice_numbers(text1)
    numbers2 = extract_invoice_numbers(text2)
    
    matching_numbers = [num for num in numbers1 if num in numbers2]
    return matching_numbers if matching_numbers else None

def process_images():
    """Process the captured images with OCR and compare them."""
    try:
        # Show loading spinner
        with st.spinner('Processing images...'):
            # Initialize OCR reader
            reader = easyocr.Reader(['en'])
            
            # Process each image
            extracted_texts = []
            for image_path in st.session_state.captured_images:
                # Process with EasyOCR
                results = reader.readtext(image_path)
                
                # Extract text
                extracted_text = ""
                for detection in results:
                    text = detection[1]
                    extracted_text += text + "\n"
                
                extracted_texts.append(extracted_text)
            
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
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("OPEN CAMERA", use_container_width=True):
            reset_captured_images()
            switch_screen('camera')
    
    with col2:
        if st.button("UPLOAD FROM GALLERY", use_container_width=True):
            reset_captured_images()
            switch_screen('upload')

def camera_screen():
    """Display the camera capture screen."""
    st.title("Camera Capture")
    st.write(f"Images Captured: {len(st.session_state.captured_images)}/2")
    
    # Streamlit has no built-in camera access, so we'll use file uploader as a workaround
    st.write("Please capture or upload an image:")
    
    image_file = st.camera_input("Take a photo")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("BACK", use_container_width=True):
            switch_screen('home')
    
    with col2:
        # This button is shown only when an image is captured
        if image_file is not None:
            if st.button("CAPTURE", use_container_width=True):
                if len(st.session_state.captured_images) >= 2:
                    st.warning("You've already captured 2 images. Processing...")
                    st.session_state.processing = True
                    process_images()
                else:
                    # Save captured image to a temporary file
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    temp_file.write(image_file.getvalue())
                    temp_file_path = temp_file.name
                    temp_file.close()
                    
                    # Add to captured images
                    st.session_state.captured_images.append(temp_file_path)
                    
                    # If we have two images, process them
                    if len(st.session_state.captured_images) == 2:
                        st.session_state.processing = True
                        process_images()
                    else:
                        st.success("Captured image 1. Please capture one more.")
                        # Refresh to clear camera input for next capture
                        st.experimental_rerun()

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
            # Limit to first 2 images if more were selected
            files_to_process = uploaded_files[:2]
            
            # Save uploaded files to temporary files
            for uploaded_file in files_to_process:
                # Save file to a temporary location
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
                temp_file.close()
                
                # Add to captured images
                st.session_state.captured_images.append(temp_file_path)
            
            # If we have more than 2 images, keep only the first 2
            if len(st.session_state.captured_images) > 2:
                st.session_state.captured_images = st.session_state.captured_images[:2]
            
            # If we have two images, process them
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
        if len(st.session_state.captured_images) > 0:
            image = PILImage.open(st.session_state.captured_images[0])
            st.image(image, use_column_width=True)
    
    with col2:
        st.subheader("Document 2")
        if len(st.session_state.captured_images) > 1:
            image = PILImage.open(st.session_state.captured_images[1])
            st.image(image, use_column_width=True)
    
    # Match status
    if st.session_state.matching_numbers:
        st.success("✅ MATCH FOUND!")
        st.write(f"Invoice Number: {st.session_state.matching_numbers[0]}")
    else:
        st.error("❌ NO MATCH FOUND")
        st.write("No matching invoice numbers between documents")
    
    # Display extracted text side by side
    text_col1, text_col2 = st.columns(2)
    
    with text_col1:
        st.subheader("Document 1 Text:")
        if len(st.session_state.extracted_texts) > 0:
            st.text_area("", value=st.session_state.extracted_texts[0], height=300)
    
    with text_col2:
        st.subheader("Document 2 Text:")
        if len(st.session_state.extracted_texts) > 1:
            st.text_area("", value=st.session_state.extracted_texts[1], height=300)
    
    # New scan button
    if st.button("NEW SCAN", use_container_width=True):
        reset_captured_images()
        switch_screen('home')

# Main app logic
def main():
    # Clean up any temporary files at startup
    # delete_jpg_images()
    
    # Show the appropriate screen based on session state
    if st.session_state.processing:
        st.spinner("Processing Images...")
        process_images()
    elif st.session_state.current_screen == 'home':
        home_screen()
    elif st.session_state.current_screen == 'camera':
        camera_screen()
    elif st.session_state.current_screen == 'upload':
        upload_screen()
    elif st.session_state.current_screen == 'comparison':
        comparison_screen()
    else:
        st.error("Unknown screen")
        switch_screen('home')

if __name__ == "__main__":
    main()