git clone git@gitlab.com:platform-rag/personalized-ai-coach.git
git clone git@gitlab.com:platform-rag/robot-ai-lesson.git
git clone git@gitlab.com:platform-rag/robot-ai-tool.git
git clone git@gitlab.com:platform-rag/robot-ai-workflow.git

git rm -rf personalized-ai-coach
git rm -rf robot-ai-lesson
git rm -rf robot-ai-tool
git rm -rf robot-ai-workflow

git submodule add git@gitlab.com:platform-rag/personalized-ai-coach.git
git submodule add git@gitlab.com:platform-rag/robot-ai-lesson.git
git submodule add git@gitlab.com:platform-rag/robot-ai-tool.git
git submodule add git@gitlab.com:platform-rag/robot-ai-workflow.git

git add .
git commit -m "Update submodule pointer for robot-ai-tool"
git push 


## **2. Khi bạn chỉ sửa code ở repo cha**

Nếu bạn chỉ sửa code ở repo cha (không sửa gì ở submodule), bạn làm việc bình thường:

```bash
# Sửa file ở repo cha (ví dụ: README.md, file cấu hình, v.v.)
git add <file>
git commit -m "Update README in parent repo"
git push
```

Lệnh này thậm chí còn push cả 4 sub repo into github. 


Giả sử bạn sửa file trong `robot-ai-tool` (submodule):

```bash
cd robot-ai-tool
git add .
git commit -m "Add a new tool function"
git push
cd ..
git add robot-ai-tool
git commit -m "Update submodule pointer for robot-ai-tool"
git push
```