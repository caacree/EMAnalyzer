// src/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/', // Adjust this base URL to match your Django server
});

export const fetchEMImages = async () => {
  const res = await api.get('em_images/');
  return res.data;
};

export const createEMImage = async (data: FormData) => {
  console.log("API called with data:", data); // Debug log
  const res = await api.post('em_images/', data);
  console.log("API response:", res.data); // Debug log
  return res.data;
};

export const deleteEMImage = async (id: string) => {
  const res = await api.delete(`em_images/${id}/`);
  return res.data;
};

export const postImageSetPoints = async (imageSetId: string, points: any[]) => {
  api.post(`mims_image_sets/${imageSetId}/submit_viewset_alignment_points/`, {points});
}

export default api;
