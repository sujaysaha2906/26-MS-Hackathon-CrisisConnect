"""Data-driven voice interview. Answers are held only for the current session."""
from .core import redact


QUESTIONS = {
    "shelter": "Do you and the people with you have a place to stay tonight?",
    "food": "Do you have enough food and drinking water for the people with you?",
    "recovery": "How has this crisis affected your home or your ability to stay there?",
    "documents": "Have you lost any documents you need? Please describe the type, without sharing any document numbers.",
    "human": "What would you want a support worker to know about your situation?",
}


class Interview:
    def __init__(self, crisis):
        self.questions = [
            f"We are discussing the {crisis['event']} in {crisis['county']}, {crisis['state']}. "
            "How has this crisis affected you?",
            "Are you on your own, or are other people with you?",
        ]
        self.questions.extend(QUESTIONS[need] for need in dict.fromkeys(crisis['expected_needs']) if need in QUESTIONS)
        self.questions.append("Is there anything else about your situation that you would like to share?")
        self.answers = []

    @property
    def complete(self):
        return len(self.answers) == len(self.questions)

    @property
    def prompt(self):
        if self.complete:
            return "Thank you for sharing your situation. That is the end of our conversation."
        return self.questions[len(self.answers)]

    def answer(self, text):
        if not text.strip():
            raise ValueError("No speech was recognized. Please record your answer again.")
        if self.complete:
            raise ValueError("The conversation is complete. Start a new conversation to continue.")
        self.answers.append(redact(text.strip()))
        return self.prompt
