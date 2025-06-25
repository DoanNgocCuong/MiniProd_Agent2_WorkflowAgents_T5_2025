import os, traceback, aiohttp, logging, copy
from .tool_grammar_checker import ToolGrammarChecker
from .tool_pronunciation_checker import ToolPronunciationChecker
from .profile_matching import ProfileMatching
from .profile_extractor import ProfileExtractor
from .image_matching import ImageMatching
from .language_matching import LanguageMatching
from .mood_matching import MoodMatching
from .check_call_tool import CheckCallTool
from .mem0_generation import Mem0Generation
from .summary_conversation import SummaryConversation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ToolExecutor:

    def __init__(self, provider_models: dict, tool_config: dict):
        self.tool_grammar_checker = ToolGrammarChecker(provider_models)
        self.tool_pronunciation_checker = ToolPronunciationChecker(
            **tool_config.get("PRONUNCIATION_CHECKER_TOOL")
        )
        self.profile_matching = ProfileMatching(
            provider_models
        )
        self.profile_extractor = ProfileExtractor(
            provider_models
        )
        self.image_matching = ImageMatching(
            provider_models
        )
        self.language_matching = LanguageMatching(
            provider_models
        )
        self.mood_matching = MoodMatching(
            provider_models
        )
        self.check_call_tool = CheckCallTool(
            provider_models
        )
        self.mem0_generation = Mem0Generation(
            provider_models
        )
        self.summary_conversation = SummaryConversation(
            provider_models
        )
        

    async def execute(self, 
        conversation_id: str, 
        tool_name: str, 
        audio_url: str = None,
        message: str = None,
        text_refs: str = None,
        question: str = None,
        **kwargs
        ) -> dict:
        try:
            if tool_name == "PRONUNCIATION_CHECKER_TOOL":
                return await self.tool_pronunciation_checker.process(
                    audio_url=audio_url,
                    message=message,
                    text_refs=text_refs,
                    **kwargs
                )
            if tool_name == "GRAMMAR_CHECKER_TOOL":
                return await self.tool_grammar_checker.process(
                    message=message,
                    question=question,
                    **kwargs
                )
        except Exception as e:
            return {
                "msg": f"Bad request {traceback.format_exc()}",
            }
        
    async def get_conversation_template(self, conversation_id: str, bot_type: str) -> list:
        try:
            url = None
            if bot_type == "Agent":
                url = copy.deepcopy(os.getenv("URL_AGENT"))
            if bot_type == "Workflow":
                url = copy.deepcopy(os.getenv("URL_WORKFLOW"))
            if bot_type == "Lesson":
                url = copy.deepcopy(os.getenv("URL_LESSON"))
            url = url + "/database/getHistoryFromConversationId"
            params = {
                "conversation_id": conversation_id,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    status = response.status
                    logging.info(f"[TOOLS][INFO] Get conversation template: {url} - {params} - {await response.text()}")
                    if status == 200:
                        output =await response.json()
                        if output and isinstance(output, dict) and isinstance(output.get("result"), list) and output.get("result"):
                            return output.get("result")
                        return None
                    else:
                        return None
        except Exception as e:
            logging.error(f"[TOOLS][ERROR] Get conversation template: {traceback.format_exc()}")
            return None