import json
import re
import logging, copy


class RegexIntentClassifier(object):
    """Module classification using lib re(Regex)"""

    def process(self, scenario: dict, message: str, next_action: int) -> None:
        try :
            if not isinstance(next_action, int) or next_action >= len(scenario):
                return None
            flows = copy.deepcopy(scenario[next_action].get("FLOWS"))

            if not isinstance(flows, dict):
                return None
            for intent_name, element in flows.items():
                for value in element:
                    regex_negative = value.get("REGEX_NEGATIVE")
                    output_negative = self.regex_pattern(
                        message = message,
                        patterns=regex_negative,
                    )
                    if output_negative == True:
                        continue
                    
                    regex_positive = value.get("REGEX_POSITIVE")
                    output_positive = self.regex_pattern(
                        message = message,
                        patterns=regex_positive,
                    )
                    if output_positive == True:
                        return intent_name
            return None
        except:
            return None
    
    def regex_pattern(self, message: str, patterns: list):
        try:
            if not isinstance(patterns, list) or not isinstance(message, str):
                return False
            for pattern in patterns:
                if isinstance(pattern, str) and len(pattern.strip()) > 0:
                    if re.match(".*{}.*".format(pattern), message, re.IGNORECASE):
                        return True
            return False
        except:
            return False

    def button_click_classifier(self, message: str, scenario: dict, next_action: int) -> str:
        try:
            if not message:
                return None
            if not isinstance(next_action, int) or next_action >= len(scenario):
                return None
            
            flows = copy.deepcopy(scenario[next_action].get("FLOWS"))
            if not isinstance(flows, dict):
                return None
            logging.info(f"===============[Button Click Classifier] flows: {flows}")
            for intent_name, element in flows.items():
                for value in element:
                    button = value.get("BUTTON")
                    if not button:
                        continue
                    if button.strip() == message.strip() or button.strip() == message[:-1].strip():
                        logging.info(f"===============[Button Click Classifier] intent_name==============: {intent_name}")
                        return intent_name
            return None
        except:
            return None