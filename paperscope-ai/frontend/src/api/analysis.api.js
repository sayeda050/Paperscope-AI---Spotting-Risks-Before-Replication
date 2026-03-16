import http from "./http";

export async function getUserDashboard() {
  const res = await http.get("/api/analysis/dashboard/");
  return res.data;
}

export async function getUserJobs() {
  const res = await http.get("/api/analysis/jobs/");
  return res.data;
}

export async function getUserHistory() {
  const res = await http.get("/api/analysis/history/");
  return res.data;
}

export async function getUserJobDetail(jobId) {
  const res = await http.get(`/api/analysis/jobs/${jobId}/`);
  return res.data;
}

export async function getUserResult(jobId) {
  const res = await http.get(`/api/analysis/results/${jobId}/`);
  return res.data;
}

export async function getAdminDashboard() {
  const res = await http.get("/api/analysis/admin/dashboard/");
  return res.data;
}

export async function getAdminUsers() {
  const res = await http.get("/api/analysis/admin/users/");
  return res.data;
}

export async function getAdminJobs() {
  const res = await http.get("/api/analysis/admin/jobs/");
  return res.data;
}

export async function retryAdminJob(jobId) {
  const res = await http.post(`/api/analysis/admin/jobs/${jobId}/retry/`, {});
  return res.data;
}

export async function getAdminResults() {
  const res = await http.get("/api/analysis/admin/results/");
  return res.data;
}

export async function getAdminResultDetail(resultId) {
  const res = await http.get(`/api/analysis/admin/results/${resultId}/`);
  return res.data;
}

export async function getAdminErrorLogs() {
  const res = await http.get("/api/analysis/admin/error-logs/");
  return res.data;
}