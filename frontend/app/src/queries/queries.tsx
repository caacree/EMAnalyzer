// src/queries.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchImages, createImage, deleteImage } from '@/api/api';
import { createCanvas, deleteCanvas, fetchCanvasList } from '../api/api';

export const useEMImagesQuery = () =>
  useQuery({
    queryKey: ['em_images'],
    queryFn: fetchImages,
  });

export const useCreateEMImageMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createImage,
    onSuccess: () => queryClient.invalidateQueries(['em_images']),
  });
};

export const useDeleteEMImageMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteImage,
    onSuccess: () => queryClient.invalidateQueries(['em_images']),
  });
};

export const useCanvasListQuery = () =>
  useQuery({
    queryKey: ['canvas_list'],
    queryFn: fetchCanvasList,
  });

export const useCreateCanvasMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCanvas,
    onSuccess: () => queryClient.invalidateQueries(['canvas_list']),
  });
}

export const useDeleteCanvasMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteCanvas,
    onSuccess: () => queryClient.invalidateQueries(['canvas_list']),
  });
}