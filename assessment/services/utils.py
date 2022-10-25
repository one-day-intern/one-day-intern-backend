def sanitize_file_format(file_format: str):
    if file_format:
        return file_format.strip('.')


def get_interactive_quiz_total_points(questions):
    total_points = 0
    for q in questions:
        total_points += q.get('points')

    return total_points
