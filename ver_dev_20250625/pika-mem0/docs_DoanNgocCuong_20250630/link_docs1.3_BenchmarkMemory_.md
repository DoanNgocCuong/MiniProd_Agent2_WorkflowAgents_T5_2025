https://docs.google.com/spreadsheets/d/19WLnJmbe3uTouMETarzl6lMGOZa7n8f5pDcLX2qxV8M/edit?gid=16017879#gid=16017879

---

https://robot-api.hacknao.edu.vn/web/admin/conversations


---

```bash
Tụi  em (e, a  @Minh Hoang Duc ) update phần Memory ạ.
 Anh  @Cuong Vu Cao  ---Luồng cũ a Hoài đang làm make sense với Workflow nhưng không make sense với Agent. 
 Cụ thể luồng cũ: 
 - Sau khi main answer được trả ra (user's query -> fast response -> main answer), main answer sẽ query trong Mem0 để REWRITE lại cho cá nhân hóa với User. 
 - Tuy nhiên luồng này khi đem qua Agent thì bị vấn đề. Cụ thể: Sau khi User's query -> main answer (LLMs).
  Sau đó mới query trong Mem0 để REWRITE lại cho cá nhân hóa với User. Cách làm này gặp vấn đề, chẳng hạn ví dụ sau: Món ăn ưa thích của tớ là gì? -> Main answer: món ăn ưa thích của cậu là táo (lúc này thì AI sẽ tự bịa ra vì chưa query trong Mem0) 
  -> Sau đó mới đến bước REWRITE (bằng việc query trong Mem0)---=> Sửa = cách: tách riêng luồng Agent ra. Cách làm tương tự RAG: User's query -> search Mem0 lấy Facts. User's query + Facts => Trả ra Response. ---
```