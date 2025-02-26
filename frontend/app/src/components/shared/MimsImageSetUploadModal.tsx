/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { X } from 'lucide-react';
import api from '@/api/api';
import { useQueryClient } from '@tanstack/react-query';

interface MimsImageSetUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  canvasId: string;
}

const MimsImageSetUploadModal: React.FC<MimsImageSetUploadModalProps> = ({
  isOpen,
  onClose,
  canvasId,
}) => {
  const [files, setFiles] = useState<File[]>([]);
  const queryClient = useQueryClient();

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFiles(Array.from(event.target.files));
    }
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      alert('Please select files to upload');
      return;
    }

    const formData = new FormData();
    
    // Add the canvas ID to the form data
    formData.append('canvas', canvasId);
  
    // Add files to the form data
    files.forEach((file, index) => {
      formData.append(`file_${index}`, file);
    });
  
    try {
      await api.post('/mims_image_set/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      // Invalidate queries to refresh data
      queryClient.invalidateQueries();
      
      // Reset form and close modal
      setFiles([]);
      onClose();
    } catch (error) {
      alert('Failed to upload files');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Add New MIMS Image Set</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X size={24} />
          </button>
        </div>
        
        <div className="mb-4">
          <label htmlFor="file-input" className="block mb-2 font-medium">
            Select MIMS image files:
          </label>
          <input
            type="file"
            id="file-input"
            multiple
            onChange={handleFileChange}
            className="w-full border border-gray-300 rounded p-2"
          />
          {files.length > 0 && (
            <p className="mt-2 text-sm text-gray-600">
              {files.length} file(s) selected
            </p>
          )}
        </div>
        
        <div className="flex justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Upload
          </button>
        </div>
      </div>
    </div>
  );
};

export default MimsImageSetUploadModal;
