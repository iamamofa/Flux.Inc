# utils/validation.py
def handle_validation_error(validation_error):
    """Convert Django ValidationError to API-friendly format"""
    errors = {}
    if hasattr(validation_error, 'error_dict'):
        # Model validation error
        for field, field_errors in validation_error.error_dict.items():
            errors[field] = [str(error) for error in field_errors]
    else:
        # Form non-field error
        errors['non_field_errors'] = [str(validation_error)]

    return errors
