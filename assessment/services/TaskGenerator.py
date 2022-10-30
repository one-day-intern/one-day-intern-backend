import json
import schedule
import time
import uuid


class TaskGenerator:
    def __init__(self):
        self.scheduler = schedule.Scheduler()
        initial_data_id = uuid.uuid4()
        self._current_returned_value = [initial_data_id, None]
        self._previous_returned_value = [initial_data_id, None]

    def _get_message_to_returned_value(self, message: dict):
        data_id = uuid.uuid4()
        message['id'] = str(data_id)
        self._current_returned_value[0] = data_id
        self._current_returned_value[1] = message
        return schedule.CancelJob

    def add_task(self, message, time_to_send):
        self.scheduler.every().day.at(time_to_send).do(self._get_message_to_returned_value, message)

    def generate(self):
        yield f'data: BEGIN TASK\n\n'
        while True:
            self.scheduler.run_pending()
            if self._current_returned_value[0] != self._previous_returned_value[0]:
                self._previous_returned_value[0] = self._current_returned_value[0]
                self._previous_returned_value[1] = self._current_returned_value[1]
                yield f'data: {json.dumps(self._current_returned_value[1])}\n\n'
            time.sleep(1)

