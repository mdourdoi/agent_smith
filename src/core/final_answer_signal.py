class FinalAnswerSignal(Exception):
    def __init__(self, answer: str):
        self.answer = answer
