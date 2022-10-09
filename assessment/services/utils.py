def sanitize_file_format(file_format: str):
    if file_format:
        return file_format.strip('.')

