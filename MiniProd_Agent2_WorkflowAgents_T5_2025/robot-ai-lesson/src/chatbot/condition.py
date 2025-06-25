from typing import List, Dict
import os, traceback
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)


class Condition:
    """
    Class để kiểm tra điều kiện dựa trên rule và input_slots
    """
    
    def __init__(self):
        """
        Khởi tạo Condition
        
        Args:
            rule (dict, optional): Quy tắc chứa thông tin điều kiện
            input_slots (dict, optional): Các giá trị của các biến
        """
        
        # Mapping các operator thành phép so sánh thực sự
        self.operator_mapping = {
            ">": self._greater_than,
            "<": self._less_than,
            ">=": self._greater_than_or_equal,
            "<=": self._less_than_or_equal,
            "!=": self._not_equal,
            "=": self._equal,
            "<>": self._not_equal,  # Tương tự !=
            "EMPTY": self._is_empty,
            "NOT_EMPTY": self._is_not_empty,
            "NO_MATCH": self._no_match
        }

    def process(self, condition, input_slots):
        """
        Xử lý điều kiện
        """
        try:
            for rule in condition:
                if self.check_condition(rule, input_slots):
                    return rule
            return None
        except Exception as e:
            logging.error(f"Error in process condition: {traceback.format_exc()}")
            return None


    def check_condition(self, rule, input_slots):
        """
        Kiểm tra điều kiện dựa trên rule
        
        Args:
            rule (dict): Quy tắc chứa thông tin điều kiện
            input_slots (dict): Các giá trị của các biến
            
        Returns:
            bool: True nếu điều kiện được thỏa mãn, False nếu không
        """
        variable_name = rule.get("variable_name")
        operator = str(rule.get("operator")).upper()
        comparison_value = rule.get("comparison_value")
        
        # Lấy giá trị của biến từ input_slots
        current_value = input_slots.get(variable_name)
        
        # Kiểm tra operator có tồn tại trong mapping không
        if operator not in self.operator_mapping:
            return False
        
        # Thực hiện phép so sánh
        return self.operator_mapping[operator](current_value, comparison_value)
    
    def _greater_than(self, current_value, comparison_value):
        """So sánh lớn hơn"""
        if current_value is None:
            return False
        try:
            return float(current_value) > float(comparison_value)
        except (ValueError, TypeError):
            return str(current_value) > str(comparison_value)
    
    def _less_than(self, current_value, comparison_value):
        """So sánh nhỏ hơn"""
        if current_value is None:
            return False
        try:
            return float(current_value) < float(comparison_value)
        except (ValueError, TypeError):
            return str(current_value) < str(comparison_value)
    
    def _greater_than_or_equal(self, current_value, comparison_value):
        """So sánh lớn hơn hoặc bằng"""
        if current_value is None:
            return False
        try:
            return float(current_value) >= float(comparison_value)
        except (ValueError, TypeError):
            return str(current_value) >= str(comparison_value)
    
    def _less_than_or_equal(self, current_value, comparison_value):
        """So sánh nhỏ hơn hoặc bằng"""
        if current_value is None:
            return False
        try:
            return float(current_value) <= float(comparison_value)
        except (ValueError, TypeError):
            return str(current_value) <= str(comparison_value)
    
    def _equal(self, current_value, comparison_value):
        """So sánh bằng"""
        if current_value is None and comparison_value is None:
            return True
        if current_value is None or comparison_value is None:
            return False
        try:
            return float(current_value) == float(comparison_value)
        except (ValueError, TypeError):
            return str(current_value) == str(comparison_value)
    
    def _not_equal(self, current_value, comparison_value):
        """So sánh không bằng"""
        return not self._equal(current_value, comparison_value)
    
    def _is_empty(self, current_value, comparison_value):
        """Kiểm tra rỗng"""
        if not current_value:
            return True
        return False
    
    def _is_not_empty(self, current_value, comparison_value):
        """Kiểm tra không rỗng"""
        return not self._is_empty(current_value, comparison_value)
    
    def _no_match(self, current_value, comparison_value):
        """Kiểm tra không khớp (string matching)"""
        return True


# Ví dụ sử dụng
if __name__ == "__main__":
    # Ví dụ rule từ yêu cầu
    rule = {
        "variable_name": "SCORE",
        "operator": ">=",
        "comparison_value": 0.5,
        "robot_type": "Workflow",
        "robot_type_id": 5
    }
    
    # Ví dụ input_slots
    input_slots = {
        "SCORE": 0.7,
        "NAME": "Test",
        "EMPTY_FIELD": "",
        "NULL_FIELD": None
    }
    
    # Tạo condition và kiểm tra với tham số
    condition = Condition()
    result = condition.check_condition(rule, input_slots)
    
    print(f"Rule: {rule}")
    print(f"Giá trị SCORE: {input_slots['SCORE']}")
    print(f"Kết quả kiểm tra: {result}")  # True vì 0.7 >= 0.5
    
    # Ví dụ khác với operator khác
    rule2 = {
        "variable_name": "EMPTY_FIELD",
        "operator": "NOT_EMPTY",
        "comparison_value": None,
        "robot_type": "Workflow",
        "robot_type_id": 5
    }
    
    result2 = condition.check_condition(rule2, input_slots)
    print(f"\nKiểm tra EMPTY: {result2}")  # True vì EMPTY_FIELD là chuỗi rỗng
