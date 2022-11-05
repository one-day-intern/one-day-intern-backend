def text_value_is_valid(request_value, min_length=0, max_length=255):
    return (
            request_value is not None and
            min_length <= len(request_value) <= max_length
    )


