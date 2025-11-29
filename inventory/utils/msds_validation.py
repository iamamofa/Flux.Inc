from difflib import SequenceMatcher
from PyPDF2 import PdfReader
from django.forms import ValidationError
from io import BytesIO


def validate_file_size(file):
    """Validator for file size"""
    limit = 5 * 1024 * 1024  # 5 MB
    if file.size > limit:
        raise ValidationError(f"File too large. Size should not exceed {limit/1024/1024}MB.")


def extract_text_from_pdf(file):
    """Extract text content from PDF"""
    text = ""
    try:
        reader = PdfReader(BytesIO(file.read()))
        for page in reader.pages:
            text += page.extract_text() + "\n"
        file.seek(0) # Reset file pointer
    except Exception as e:
        raise ValidationError(f"Error reading PDF: {str(e)}")
    return text


def validate_msds_content(msds_file):
    """Validate MSDS content against required sections"""
    from ..models import MSDSSection, MSDSValidateResult

    text = extract_text_from_pdf(msds_file.file)
    sections = MSDSSection.objects.filter(required=True).order_by('order')
    results = []

    for section in sections:
        keywords = [k.strip().lower() for k in section.keywords.split(',') if k.strip()]
        best_match = None
        best_ratio = 0

        # Search for section headers
        for keyword in keywords:
            # Simple search for keyword
            if keyword in text.lower():
                best_ratio = 1.0
                break

            # More sophisticated fuzzy matching if simple search fails
            words = text.lower().split()
            for i in range(len(words) - len(keyword.split()) + 1):
                window = ' '.join(words[i+i+len(keyword.split())])
                ratio = SequenceMatcher(None, keyword, window).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    if ratio > 0.8:  # God enough match
                        break

        found = best_ratio > 0.8
        results.append(MSDSValidateResult(
            msds_file=msds_file,
            section=section,
            found=found,
            match_quality=best_ratio,
            extract_text=text[:500] if found else ""  # Store snippet if found
        ))

    # Save all results
    MSDSValidateResult.objects.bulk_create(results)

    # Mark file as verified if all required sections found
    all_required_found = all(r.found for r in results if r.section.required)
    msds_file.is_verified = all_required_found
    msds_file.save()

    return all_required_found
