from typing import Dict
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents"""
    def __init__(self, name: str):
        self.name = name

    async def process(self, context: Dict) -> Dict:
        """Process method to be implemented by specific agents"""
        raise NotImplementedError
