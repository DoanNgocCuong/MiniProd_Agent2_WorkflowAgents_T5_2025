import asyncio
import json
import os
import yaml
import aiohttp
from datetime import datetime
from typing import List, Dict, Tuple

# API Configuration
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "9330"))
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/robot-ai-tool/api/v1/tool"

# Load test cases from generated file
def load_test_cases(filename: str) -> List[Dict]:
    """Load test cases from a JSON file"""
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("test_cases", [])

async def call_property_matching_api(session: aiohttp.ClientSession, conversation: List[Dict], bot_id: int = 19543066) -> Dict:
    """Call the property matching API endpoint"""
    url = f"{API_BASE_URL}/properityMatching"
    payload = {
        "conversation_id": f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "tool_name": "matching",
        "messages": conversation,
        "bot_id": bot_id
    }
    
    try:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                print(f"API Error: Status {response.status}")
                return None
            
            result = await response.json()
            if result.get("status") == 0:
                return result.get("result", {})
            else:
                print(f"API Error: {result.get('msg')}")
                return None
    except Exception as e:
        print(f"API Call Error: {str(e)}")
        return None

async def run_benchmark(test_cases_file: str = None):
    if test_cases_file is None:
        # Use the most recent test cases file if none specified
        import glob
        files = glob.glob("language_matching_testcases_*.json")
        if not files:
            print("No test cases file found. Please run gen_testcase.py first.")
            return
        test_cases_file = max(files, key=os.path.getctime)
    
    test_cases = load_test_cases(test_cases_file)
    results = []
    
    print("\n=== Property Matching API Benchmark Results ===\n")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"API URL: {API_BASE_URL}\n")
    print(f"Using test cases from: {test_cases_file}\n")
    
    async with aiohttp.ClientSession() as session:
        for test_case in test_cases:
            try:
                predicted = await call_property_matching_api(session, test_case["conversation"])
                if predicted is None:
                    print(f"Failed to get prediction for test case: {test_case['name']}")
                    continue
                
                predicted_language = predicted.get("language")
                is_correct = predicted_language == test_case["expected"]
                
                result = {
                    "test_name": test_case["name"],
                    "expected": test_case["expected"],
                    "predicted": predicted_language,
                    "correct": is_correct,
                    "full_response": predicted
                }
                results.append(result)
                
                # Print individual test result
                print(f"Test: {test_case['name']}")
                print(f"Expected: {test_case['expected']}")
                print(f"Predicted: {predicted_language}")
                print(f"Status: {'✓ Correct' if is_correct else '✗ Incorrect'}")
                print("-" * 50)
                
            except Exception as e:
                print(f"Error in test case '{test_case['name']}': {str(e)}")
                results.append({
                    "test_name": test_case["name"],
                    "error": str(e)
                })
    
    # Calculate statistics
    total_tests = len(results)
    correct_tests = sum(1 for r in results if r.get("correct", False))
    accuracy = (correct_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print("\n=== Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Correct predictions: {correct_tests}")
    print(f"Accuracy: {accuracy:.2f}%")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"property_matching_benchmark_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "api_url": API_BASE_URL,
            "test_cases_file": test_cases_file,
            "total_tests": total_tests,
            "correct_predictions": correct_tests,
            "accuracy": accuracy,
            "detailed_results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run property matching benchmark")
    parser.add_argument("--test-cases", type=str, help="Path to test cases file (optional)")
    parser.add_argument("--bot-id", type=int, default=19543066, help="Bot ID to use for testing")
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(args.test_cases))

if __name__ == "__main__":
    main() 