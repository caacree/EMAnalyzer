// src/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/', // Adjust this base URL to match your Django server
});

export const fetchCanvasList = async () => {
  const res = await api.get('canvas/');
  return res.data;
}

export const createCanvas = async (data: FormData) => {
  const res = await api.post('canvas/', data);
  return res.data;
}

export const deleteCanvas = async (id: string) => {
  const res = await api.delete(`canvas/${id}/`);
  return res.data;
}

export const fetchImages = async () => {
  const res = await api.get('image/');
  return res.data;
};

export const createImage = async (data: FormData) => {
  console.log("API called with data:", data); // Debug log
  const res = await api.post('image/', data);
  console.log("API response:", res.data); // Debug log
  return res.data;
};

export const deleteImage = async (id: string) => {
  const res = await api.delete(`image/${id}/`);
  return res.data;
};

export const postImageSetPoints = async (imageSetId: string, points: any, isotope: string) => {
  return api.post(`mims_image_set/${imageSetId}/submit_viewset_alignment_points/`, {points, isotope});
}

export const get_mims_image_dewarped_url = (mimsImage: any, tiffImage: any) => {
  const mimsName = mimsImage.name || mimsImage.file.split('/').pop().split('.')[0];
  return `http://localhost:8000/api/mims_image/${mimsImage.id}/unwarped/${tiffImage.id}/${mimsName}_${tiffImage.name.replace(/ /g,'')}.png/`;
}

export default api;
