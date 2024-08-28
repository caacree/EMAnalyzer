import React, { useState } from "react";
import { useCanvasListQuery, useCreateCanvasMutation, useDeleteCanvasMutation } from "@/queries/queries";
import { Link } from "@tanstack/react-router";
import { TrashIcon } from "lucide-react";
import {createCanvas, createImage} from "../api/api";
import { useQueryClient } from "@tanstack/react-query";

const Dashboard = () => {
  const { data: canvases, isLoading } = useCanvasListQuery();
  const queryClient = useQueryClient();
  const createCanvasMutation = useCreateCanvasMutation();
  const deleteCanvasMutation = useDeleteCanvasMutation();

  const [file, setFile] = useState<File | null>(null);
  const [friendlyName, setFriendlyName] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (friendlyName) {
      const formData = new FormData();
      formData.append('name', friendlyName);
      createCanvas(formData).then((res) => {
        if (file) {
          const imageFormData = new FormData();
          imageFormData.append('file', file);
          imageFormData.append('canvas', res.id);
          return createImage(imageFormData).then((res: any) => {
            console.log(res);
          });
        }
      }).then(() => {
        queryClient.invalidateQueries(['canvas_list']);
        setFile(null);
        setFriendlyName('');
      });
    }
  };

  const handleDelete = (id: string) => {
    deleteCanvasMutation.mutate(id, {
      onSuccess: () => {
        console.log(`Deleted canvas with id: ${id}`); // Debug log
      },
      onError: (error: any) => {
        console.error(`Error deleting canvas with id: ${id}`, error); // Debug log
      }
    });
  };
  
  return (
    <div className="flex flex-col w-full max-w-[500px] m-auto bg-background p-4 gap-4">
      <h1>Dashboard</h1>
      <div>
        <h2>Existing Canvases</h2>
        {isLoading ? (
          <p>Loading...</p>
        ) : (
          <ul>
            {canvases?.sort((a: any, b: any) => a.name.localeCompare(b.name)).map((canvas: any) => (
              <li key={canvas.id} className="flex items-center space-x-2">
                <Link to={`/canvas/${canvas.id}`} className="flex-grow">{canvas.name}</Link>
                <button onClick={() => handleDelete(canvas.id)}>
                  <TrashIcon />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h2>Create a New Project</h2>
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
              File: {file?.name}
              <input
                type="file"
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
              />
            </label>
          </div>
          <button type="submit" disabled={createCanvasMutation.isLoading}>
            {createCanvasMutation?.isLoading ? 'Uploading...' : 'Create'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Dashboard;