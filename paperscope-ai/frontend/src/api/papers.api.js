import http from "./http";

export async function submitPdfPaper({ title, file }) {
  const formData = new FormData();

  if (title && title.trim()) {
    formData.append("title", title.trim());
  }

  formData.append("file", file);

  const res = await http.post("/api/papers/submit-pdf/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return res.data;
}

export async function submitArxivPaper({ title, arxivLink }) {
  const payload = {
    arxiv_link: arxivLink,
  };

  if (title && title.trim()) {
    payload.title = title.trim();
  }

  const res = await http.post("/api/papers/submit-arxiv/", payload);
  return res.data;
}

export async function getMyPapers() {
  const res = await http.get("/api/papers/mine/");
  return res.data;
}

export async function getAdminPapers() {
  const res = await http.get("/api/papers/admin/");
  return res.data;
}

export async function getPaperDetail(paperId) {
  const res = await http.get(`/api/papers/${paperId}/`);
  return res.data;
}

export async function getPaperText(paperId) {
  const res = await http.get(`/api/papers/${paperId}/text/`);
  return res.data;
}