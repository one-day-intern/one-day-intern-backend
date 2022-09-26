def validate_user_registration_data(request_data):
    raise Exception('Dummy Exception')


def validate_user_company_registration_data(request_data):
    raise Exception('Dummy Exception')


def save_company_from_request_data(request_data):
    return None


def register_company(request_data):
    validate_user_registration_data(request_data)
    validate_user_company_registration_data(request_data)
    company = save_company_from_request_data(request_data)
    return company
