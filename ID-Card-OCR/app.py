"""Streamlit user interface for ID Card OCR and Information Extraction."""

from __future__ import annotations

import json
import re
from datetime import datetime, date

import streamlit as st
from PIL import Image, UnidentifiedImageError

from src.service import ExtractionError, extract_from_bytes


# --------------------------------------------------
# AGE CALCULATION
# --------------------------------------------------
def calculate_age(dob_value):
    """
    DOB ko multiple formats mein parse karke current age calculate karta hai.
    Example:
    12/05/2000 -> 26 Years
    """

    if not dob_value or str(dob_value).strip().lower() in [
        "not detected",
        "unknown",
        "none",
        "null",
        "",
    ]:
        return "Not detected"

    dob_text = str(dob_value).strip()

    # OCR se extra text aaya ho to date extract karo
    date_match = re.search(
        r"(\d{1,2}[-/.\s]\d{1,2}[-/.\s]\d{4})",
        dob_text
    )

    if date_match:
        dob_text = date_match.group(1)

    # Possible DOB formats
    date_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d %m %Y",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y.%m.%d",
    ]

    birth_date = None

    for date_format in date_formats:
        try:
            birth_date = datetime.strptime(
                dob_text,
                date_format
            ).date()
            break
        except ValueError:
            continue

    if birth_date is None:
        return "Could not calculate"

    today = date.today()

    # Future DOB invalid hai
    if birth_date > today:
        return "Invalid DOB"

    age = (
        today.year
        - birth_date.year
        - (
            (today.month, today.day)
            < (birth_date.month, birth_date.day)
        )
    )

    return f"{age} Years"


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="ID Card OCR",
    page_icon="🪪",
    layout="wide"
)

st.title("AI-Based ID Card OCR & Information Extraction")

st.caption(
    "Upload an Indian identity-card image. "
    "Files are processed in memory and are not stored by this app."
)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.subheader("Privacy")

    show_full_aadhaar = st.checkbox(
        "Show full ID number",
        value=False,
        help="Leave unchecked to mask Aadhaar, PAN, and Driving Licence numbers.",
    )


# --------------------------------------------------
# FILE UPLOAD
# --------------------------------------------------
st.header("1. Upload ID Card")

uploaded_file = st.file_uploader(
    "Choose a JPG, JPEG, or PNG image",
    type=["jpg", "jpeg", "png"]
)


# --------------------------------------------------
# PROCESS FILE
# --------------------------------------------------
if uploaded_file is not None:

    try:
        image_bytes = uploaded_file.getvalue()
        preview = Image.open(uploaded_file)

        st.header("2. Image Preview")

        st.image(
            preview,
            caption="Uploaded ID card",
            use_container_width=True
        )

    except (UnidentifiedImageError, OSError):

        image_bytes = b""

        st.error(
            "This image is corrupted or invalid. "
            "Please choose another JPG, JPEG, or PNG file."
        )


    # --------------------------------------------------
    # EXTRACT BUTTON
    # --------------------------------------------------
    if st.button(
        "Extract Information",
        type="primary",
        use_container_width=True
    ):

        if not image_bytes:

            st.warning(
                "Please upload a valid image before extracting information."
            )

        else:

            try:

                with st.spinner(
                    "Removing QR code patterns, reading text, "
                    "extracting fields, and calculating age..."
                ):

                    result = extract_from_bytes(
                        image_bytes,
                        show_full_id=show_full_aadhaar
                    )

                data = result["data"]


                # --------------------------------------------------
                # CALCULATE AGE FROM DOB
                # --------------------------------------------------
                dob_value = (
                    data.get("dob")
                    or data.get("date_of_birth")
                    or data.get("DOB")
                    or data.get("Date Of Birth")
                )

                age_value = calculate_age(dob_value)


                # --------------------------------------------------
                # CREATE ORDERED OUTPUT
                # DOB KE JUST NICHE AGE ADD HOGI
                # --------------------------------------------------
                display_data = {}

                for key, value in data.items():

                    display_data[key] = value

                    # Agar current field DOB hai,
                    # turant uske niche Age add karo
                    if key.lower() in [
                        "dob",
                        "date_of_birth",
                        "date of birth",
                    ]:
                        display_data["age"] = age_value


                # Agar DOB field detect nahi hua
                # to Age bhi show nahi karenge
                if not any(
                    key.lower() in [
                        "dob",
                        "date_of_birth",
                        "date of birth",
                    ]
                    for key in data.keys()
                ):
                    age_value = "Not detected"


                # --------------------------------------------------
                # DOCUMENT TYPE
                # --------------------------------------------------
                st.header("3. Document Type")

                st.success(
                    data["document_type"]
                    if data.get("document_type") != "Unknown"
                    else "Unknown / low confidence"
                )


                # --------------------------------------------------
                # OCR PROCESSING
                # --------------------------------------------------
                st.header("4. OCR Processing")

                st.caption(
                    "Completed: preprocessing → QR masking → "
                    "Tesseract OCR → document-specific validation"
                )


                # --------------------------------------------------
                # EXTRACTED INFORMATION
                # --------------------------------------------------
                st.header("5. Extracted Information")

                table_data = [
                    {
                        "Field": key.replace("_", " ").title(),
                        "Value": value
                    }
                    for key, value in display_data.items()
                ]

                st.table(table_data)


                # --------------------------------------------------
                # RAW OCR TEXT
                # --------------------------------------------------
                st.header("6. Raw OCR Text")

                with st.expander("Show raw OCR output"):
                    st.text(result["raw_ocr_text"])


                # --------------------------------------------------
                # DOWNLOAD RESULT
                # --------------------------------------------------
                st.header("7. Download Result")

                download_payload = json.dumps(
                    {
                        "status": result["status"],
                        "data": display_data
                    },
                    indent=2
                )

                st.download_button(
                    "Download JSON",
                    download_payload,
                    file_name="id_card_extraction.json",
                    mime="application/json"
                )


            except ExtractionError as exc:
                st.error(str(exc))

            except Exception:
                st.error(
                    "The image could not be processed. "
                    "Check the image and Tesseract configuration, "
                    "then try again."
                )


else:

    st.info(
        "Upload a JPG, JPEG, or PNG image to begin."
    )