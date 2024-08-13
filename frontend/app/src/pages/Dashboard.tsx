import React, { useState } from "react";
import { useEMImagesQuery, useCreateEMImageMutation, useDeleteEMImageMutation } from "@/queries/queries";
import { Link } from "@tanstack/react-router";
import { TrashIcon } from "lucide-react";

const Dashboard = () => {
  const { data: emImages, isLoading } = useEMImagesQuery();
  const createEMImageMutation = useCreateEMImageMutation();
  const deleteEMImageMutation = useDeleteEMImageMutation();

  const [file, setFile] = useState<File | null>(null);
  const [friendlyName, setFriendlyName] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (file && friendlyName) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('friendly_name', friendlyName);
      createEMImageMutation.mutate(formData);
    }
  };

  const handleDelete = (id: string) => {
    deleteEMImageMutation.mutate(id, {
      onSuccess: () => {
        console.log(`Deleted image with id: ${id}`); // Debug log
      },
      onError: (error) => {
        console.error(`Error deleting image with id: ${id}`, error); // Debug log
      }
    });
  };
  
  return (
    <div className="flex flex-col w-full max-w-[500px] m-auto bg-background p-4">
      <h1>Dashboard</h1>
      <div>
        <h2>Existing EMImages</h2>
        {isLoading ? (
          <p>Loading...</p>
        ) : (
          <ul>
            {emImages.sort((a: any, b: any) => a.friendly_name.localeCompare(b.friendly_name)).map((image: any) => (
              <li key={image.id} className="flex items-center space-x-2">
                <Link to={`/em_image/${image.id}`} className="flex-grow">{image.friendly_name}</Link>
                <button onClick={() => handleDelete(image.id)}>
                  <TrashIcon />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h2>Create New EMImage</h2>
        <form onSubmit={handleSubmit}>
          <div>
            <label>
              Friendly Name:
              <input
                type="text"
                value={friendlyName}
                onChange={(e) => setFriendlyName(e.target.value)}
                required
              />
            </label>
          </div>
          <div>
            <label>
              File:
              <input
                type="file"
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
                required
              />
            </label>
          </div>
          <button type="submit" disabled={createEMImageMutation.isLoading}>
            {createEMImageMutation.isLoading ? 'Uploading...' : 'Create'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Dashboard;