// src/queries.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchEMImages, createEMImage, deleteEMImage } from '@/api/api';

export const useEMImagesQuery = () =>
  useQuery({
    queryKey: ['em_images'],
    queryFn: fetchEMImages,
  });

export const useCreateEMImageMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createEMImage,
    onSuccess: () => queryClient.invalidateQueries(['em_images']),
  });
};

export const useDeleteEMImageMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteEMImage,
    onSuccess: () => queryClient.invalidateQueries(['em_images']),
  });
};
