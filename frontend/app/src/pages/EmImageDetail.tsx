/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from "@tanstack/react-router";
import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { BASE_URL, buildMediaURL } from "@/api/api";
import OpenSeaDragon from '@/components/shared/OpenSeaDragon';

const fetchEMImageDetail = async (id: string) => {
  const res = await api.get(`em_images/${id}/`);
  return res.data;
};

const EMImageDetail = () => {
  const params = useParams({ strict: false });
  const queryClient = useQueryClient();
  const { emImageId } = params;
  const { data: image, isLoading } = useQuery({
    queryKey: ['em_image', emImageId as string],
    queryFn: () => fetchEMImageDetail(emImageId as string),
  });

  const [files, setFiles] = useState<File[]>([]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFiles(Array.from(event.target.files));
    }
  };

  const handleSubmit = async () => {
    const formData = new FormData();
    
    // Add the EM image ID to the form data
    formData.append('em_image', image.id);
  
    // Add files to the form data
    files.forEach((file, index) => {
      formData.append(`file_${index}`, file);
    });
  
    try {
      await api.post('/mims_image_sets/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }).then(() => queryClient.invalidateQueries());
    } catch (error) {
      alert('Failed to upload files');
    }
  };
  

  if (isLoading) {
    return <p>Loading...</p>;
  }

  return (
    <div className="w-full flex flex-col ml-10 gap-5">
      <h2>EM Image: {image.friendly_name}</h2>
      <div className="flex w-full gap-5">
        <OpenSeaDragon iiifContent={buildMediaURL(image.dzi_file)} />
        <div className="flex flex-col gap-3">
          <div>MIMS Image sets</div>
          {image?.mims_sets?.map((mimsImageSet: any) => (
            <div>
              <div className="flex gap-1">
                <div>Image set</div>
                <button>{mimsImageSet?.canvas_x && mimsImageSet?.canvas_y ? 'Aligned' : 'Unaligned'}</button>
              </div>
              {mimsImageSet.mims_images?.map((mims: any) => (
                <div>
                  <div>File: {mims.file}</div>
                </div>
              ))}
            </div>
          ))}
          <label htmlFor="file-input">Add new MIMS image set:</label>
          <input
            type="file"
            id="file-input"
            multiple
            onChange={handleFileChange}
            className="mb-2"
          />
          <button
            onClick={handleSubmit}
            className="bg-blue-500 text-white px-4 py-2 rounded"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
};
export default EMImageDetail;