# Xoá thư mục .git trong tất cả các cấp
find . -type d -name .git -exec rm -rf {} +
# Xoá file .git (nếu có)
find . -type f -name .git -exec rm -f {} +
# Xoá file .gitmodules nếu chỉ còn để lại
rm -f .gitmodules