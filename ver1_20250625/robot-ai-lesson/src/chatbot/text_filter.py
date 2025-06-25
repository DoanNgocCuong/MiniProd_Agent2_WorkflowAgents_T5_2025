import re
import json
import logging
from typing import Dict, List, Tuple, Optional
from .text_filter_config import FILTERED_WORDS, FIXED_RESPONSES, MAX_HISTORY_PER_CONVERSATION
import random

class TextFilter:
    def __init__(self):
        # Words and phrases to filter out
        self.filtered_words = FILTERED_WORDS
        
        # Fixed responses for incorrect inputs
        self.fixed_responses = FIXED_RESPONSES
        
        # Track user inputs to detect repetition
        self.user_input_history = {}
        
        # Track incorrect inputs to allow them after second occurrence
        self.incorrect_input_count = {}
        
    def filter_text(self, text: str, conversation_id: str) -> Tuple[str, bool, Optional[str]]:
        """
        Filter text and handle incorrect inputs.
        
        Args:
            text: The input text to filter
            conversation_id: The conversation ID to track user inputs
            
        Returns:
            Tuple containing:
            - The filtered text (or original if no filtering needed)
            - Boolean indicating if the text was filtered
            - Optional fixed response if the input is incorrect
        """
        if not text:
            return text, False, None
            
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # Initialize tracking for this conversation if needed
        if conversation_id not in self.user_input_history:
            self.user_input_history[conversation_id] = []
        if conversation_id not in self.incorrect_input_count:
            self.incorrect_input_count[conversation_id] = {}
            
        # Check if this is a repeated input
        if text in self.user_input_history[conversation_id]:
            # If it's repeated, we consider it valid and pass it through
            logging.info(f"Repeated input detected for conversation {conversation_id}: {text}")
            return text, False, None
            
        # Add to history
        self.user_input_history[conversation_id].append(text)
        
        # Limit history size
        if len(self.user_input_history[conversation_id]) > MAX_HISTORY_PER_CONVERSATION:
            self.user_input_history[conversation_id] = self.user_input_history[conversation_id][-MAX_HISTORY_PER_CONVERSATION:]
        
        # Check if text contains any filtered words
        for word in self.filtered_words:
            if word.lower() in text_lower:
                # Track this incorrect input
                if word not in self.incorrect_input_count[conversation_id]:
                    self.incorrect_input_count[conversation_id][word] = 1
                else:
                    self.incorrect_input_count[conversation_id][word] += 1
                
                # If this is the second or more occurrence, allow it to pass through
                if self.incorrect_input_count[conversation_id][word] >= 2:
                    logging.info(f"Allowing filtered word '{word}' to pass through after multiple occurrences")
                    return text, False, None
                
                # Replace the filtered word with empty string
                filtered_text = re.sub(re.escape(word), "", text, flags=re.IGNORECASE)
                # Clean up any double spaces
                filtered_text = re.sub(r'\s+', ' ', filtered_text).strip()
                
                # Return appropriate fixed response based on the filtered word
                fixed_response = None
                if "lala school" in text_lower:
                    fixed_response = random.choice(self.fixed_responses["lala_school"])
                elif "nghiền mì gõ" in text_lower:
                    fixed_response = random.choice(self.fixed_responses["nghien_mi_go"])
                else:
                    fixed_response = self.fixed_responses["default"]
                    
                return filtered_text, True, fixed_response
            
        # If we get here, the text is valid and not filtered
        return text, False, None
        
    def clear_history(self, conversation_id: str) -> None:
        """Clear the input history for a conversation"""
        if conversation_id in self.user_input_history:
            del self.user_input_history[conversation_id]
        if conversation_id in self.incorrect_input_count:
            del self.incorrect_input_count[conversation_id] 