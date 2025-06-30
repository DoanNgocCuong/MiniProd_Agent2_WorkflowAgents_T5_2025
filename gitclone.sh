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
git submodule add https://gitlab.com/platform-rag/pika-mem0.git

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

# Khi clone repo cha
Trên dev: file .gitmodules có đường dẫn. 
# [submodule "pika-mem0"]
# 	path = pika-mem0
# 	url = https://gitlab.com/platform-rag/pika-mem0.git

```bash
git clone https://github.com/DoanNgocCuong/MiniProd_Agent2_WorkflowAgents_T5_2025
git submodule update --init --recursive
```