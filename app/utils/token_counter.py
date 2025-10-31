"""
Token counting utilies for context budget management
"""
from typing import List

import tiktoken

import logging
logger = logging.getLogger(__name__)


class TokenCounter():
    """Utility class for counting tokens"""

    def __init__(self, model: str="gpt-4"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except Exception as e:
            logger.warning("Coult not intialise titoken, using fallback", extra={"model": model})
            # Fallback to cl100k_base encoding
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Uses tiktoken to count the number of tokens in a string

        Args:
            text: Text to count tokens

        Returns
            token count
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))
    

    
        

