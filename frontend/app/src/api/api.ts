// src/api.ts
import axios from 'axios';

export const BASE_URL = 'http://localhost:8000';
export const API_BASE_URL = `${BASE_URL}/api/`;

// Utility function to safely build media URLs
export const buildMediaURL = (url: string | null | undefined): string => {
  if (!url) return '';
  
  // If URL is already absolute (starts with http/https), return as-is
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  
  // If URL is relative (starts with /media/), prepend BASE_URL
  if (url.startsWith('/media/')) {
    return BASE_URL + url;
  }
  
  // If URL is just a path without /media/, assume it needs full media URL construction
  return `${BASE_URL}/media/${url}`;
};

const api = axios.create({
  baseURL: API_BASE_URL, // Adjust this base URL to match your Django server
});

export const fetchCanvasList = async () => {
  const res = await api.get('canvas/');
  return res.data;
}

export const createCanvas = async (data: FormData) => {
  const res = await api.post('canvas/', data);
  return res.data;
}

export const updateCanvas = async (id: string, data: { name: string }) => {
  const res = await api.patch(`canvas/${id}/`, data);
  return res.data;
}

export const deleteCanvas = async (id: string) => {
  const res = await api.delete(`canvas/${id}/`);
  return res.data;
}

// Segmentation API functions
export const uploadSegmentationFile = async (data: FormData) => {
  const res = await api.post('segmentation-files/', data, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return res.data;
}

export const fetchSegmentationFiles = async (canvasId: string) => {
  const res = await api.get(`segmentation-files/?canvas_id=${canvasId}`);
  return res.data;
}

export const deleteSegmentationFile = async (id: string) => {
  const res = await api.delete(`segmentation-files/${id}/`);
  return res.data;
}

export const fetchSegmentedObjects = async (canvasId: string, sourceFileId?: string) => {
  let url = `segmented-objects/?canvas_id=${canvasId}`;
  if (sourceFileId) {
    url += `&source_file_id=${sourceFileId}`;
  }
  const res = await api.get(url);
  return res.data;
}

export const fetchSegmentationStats = async (canvasId: string) => {
  const res = await api.get(`segmentation-files/stats/?canvas_id=${canvasId}`);
  return res.data;
}

export const fetchSegmentationProgress = async (id: string) => {
  const res = await api.get(`segmentation-files/${id}/progress/`);
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
  return `${API_BASE_URL}mims_image/${mimsImage.id}/unwarped/${tiffImage.id}/${mimsName}_${tiffImage.name.replace(/ /g,'')}.png/`;
}

export default api;
