import aiohttp, os, logging, traceback


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ToolPronunciationChecker:

    def __init__(self, url: str, headers: dict = {}, token: str = None, timeout = None, **kwargs):
        self.url = url
        self.token = token
        self.headers = headers
        self.timeout = timeout

    async def process(self,
        audio_url: str = None,
        message: str = None,
        text_refs: str = None,
        **kwargs):

        try :
            async with aiohttp.ClientSession() as session:
                logging.info(f"[TOOLS][INFO] Request Tool: {self.url}")
                if audio_url:
                    async with session.get(audio_url) as audio_response:
                        if audio_response.status == 200:
                            audio_data = await audio_response.read()  # Read audio data as bytes

                            # Prepare FormData with the downloaded audio data
                            form_data = aiohttp.FormData()
                            form_data.add_field('audio-file', audio_data, filename=audio_url.split("/")[-1], content_type='audio/wav')
                            form_data.add_field('text-refs', text_refs)
                            form_data.add_field('token', self.token)
                            # Now send the audio file along with payload to the API
                            # logging.info(f"[TOOLS][INFO] Request Tool: {url} - form_data: {form_data}")
                            async with session.post(self.url, data=form_data, timeout=self.timeout, headers=self.headers) as response:
                                response_json = await response.json()
                                metadata = kwargs.get("metadata", {})
                                if isinstance(metadata, dict):
                                    threshold = metadata.get("threshold", 0.5)
                                else :
                                    threshold = 0.5
                                result = self.extract_pronunciation(response_json, text_refs=text_refs, threshold=threshold)
                                if not isinstance(result, dict):
                                    return None
                                result["target"] = text_refs
                                return result
        except Exception as e:
            return {
                "msg": f"Bad request {traceback.format_exc()}",
            }

    
    def extract_pronunciation(self, data: dict, threshold = 0.5, text_refs = "") -> dict:
        try:
            if not isinstance(data, dict):
                return None
            error = []
            word_pronunciation_error = []
            result = {
                "feedback": None,
                "pronunciation_words": [],
                "pronunciation_sentences": 0.0
            }
            for element in data.get("result"):
                word = element.get("word")
                score = element.get("score")
                result["pronunciation_words"].append({
                    "word": word,
                    "score": score,
                    "phones": element.get("phones", [])
                })
                result["pronunciation_sentences"] += score
                if score <= threshold:
                    if isinstance(element.get("phones"), list):
                        phones_error = []
                        for phone in element.get("phones"):
                            if phone.get("score") <= threshold:
                                phone_ipa = phone.get("phone_ipa")
                                phones_error.append(f"/{phone_ipa}/")
                        phones_error = f"Âm*# {' , '.join(phones_error)}"
                        word_pronunciation_error.append(f"{phones_error} *#trong từ {word}")
                    else :
                        word_pronunciation_error.append(word)
            
            result["pronunciation_sentences"] = result["pronunciation_sentences"] / len(data.get("result")) if len(data.get("result")) > 0 else None
            if len(word_pronunciation_error) > 0:
                word_pronunciation_error = ", ".join(word_pronunciation_error)
                output = "*#Có 1 số từ phát âm chưa đúng: " + word_pronunciation_error + ". " + f"Thử lại nhé: {text_refs}.*#" 
                logging.info(f"[TOOLS][INFO] Pronunciation output: {output}")
                result["feedback"] = output.strip()
            return result
                        
            # logging.info(f"[TOOLS][INFO] Pronunciation error: {error}")
        except Exception as e:
            return {
                "feedback": None,
                "pronunciation": []
            }