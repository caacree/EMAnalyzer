import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/shared/ui/dialog';
import { Button } from '@/components/shared/ui/button';
import { Input } from '@/components/shared/ui/input';
import { Label } from '@/components/shared/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/shared/ui/radio-group';
import { Slider } from '@/components/shared/ui/slider';
import { uploadSegmentationFile } from '@/api/api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, AlertCircle } from 'lucide-react';

interface SegmentationUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  canvasId: string;
}

const SegmentationUploadModal: React.FC<SegmentationUploadModalProps> = ({
  isOpen,
  onClose,
  canvasId,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [uploadType, setUploadType] = useState<'probability' | 'label'>('probability');
  const [threshold, setThreshold] = useState(0.5);
  const [minArea, setMinArea] = useState(10);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: uploadSegmentationFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segmentations', canvasId] });
      queryClient.invalidateQueries({ queryKey: ['canvas', canvasId] });
      handleReset();
      onClose();
    },
    onError: (error: any) => {
      setError(error.response?.data?.error || 'Failed to upload segmentation file');
      setIsUploading(false);
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      const fileName = selectedFile.name.toLowerCase();
      if (!fileName.endsWith('.tif') && !fileName.endsWith('.tiff') && !fileName.endsWith('.png')) {
        setError('Please select a TIFF or PNG file (.tif, .tiff, or .png)');
        return;
      }
      setFile(selectedFile);
      setError('');
      
      // Auto-fill name from filename if empty
      if (!name) {
        const baseName = selectedFile.name.replace(/\.(tif|tiff|png)$/i, '');
        setName(baseName);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file) {
      setError('Please select a file');
      return;
    }
    
    if (!name.trim()) {
      setError('Please enter a name for the segmentation');
      return;
    }

    setIsUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('canvas', canvasId);
    formData.append('name', name.trim());
    formData.append('upload_type', uploadType);
    
    if (uploadType === 'probability') {
      formData.append('threshold', threshold.toString());
      formData.append('min_area', minArea.toString());
    }

    uploadMutation.mutate(formData);
  };

  const handleReset = () => {
    setFile(null);
    setName('');
    setUploadType('probability');
    setThreshold(0.5);
    setMinArea(10);
    setError('');
    setIsUploading(false);
  };

  const handleClose = () => {
    if (!isUploading) {
      handleReset();
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Segmentation</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* File Input */}
          <div className="space-y-2">
            <Label htmlFor="file">Segmentation File (TIFF or PNG)</Label>
            <div className="flex items-center space-x-2">
              <Input
                id="file"
                type="file"
                accept=".tif,.tiff,.png"
                onChange={handleFileChange}
                disabled={isUploading}
                className="flex-1"
              />
              {file && (
                <Upload className="w-4 h-4 text-green-500" />
              )}
            </div>
            {file && (
              <p className="text-sm text-gray-500">
                Selected: {file.name}
              </p>
            )}
          </div>

          {/* Name Input */}
          <div className="space-y-2">
            <Label htmlFor="name">Segmentation Name</Label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., mitochondria, cells"
              disabled={isUploading}
            />
            <p className="text-xs text-gray-500">
              This will be the object type name (e.g., "mitochondria", "cells")
            </p>
          </div>

          {/* Upload Type Selection */}
          <div className="space-y-2">
            <Label>Upload Type</Label>
            <RadioGroup
              value={uploadType}
              onValueChange={(value) => setUploadType(value as 'probability' | 'label')}
              disabled={isUploading}
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="probability" id="probability" />
                <Label htmlFor="probability" className="font-normal cursor-pointer text-gray-700">
                  Probability Map (0-1 values)
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="label" id="label" />
                <Label htmlFor="label" className="font-normal cursor-pointer text-gray-700">
                  Label Map (pre-segmented objects)
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Probability Map Parameters */}
          {uploadType === 'probability' && (
            <>
              <div className="space-y-2">
                <Label htmlFor="threshold">Threshold (0-1)</Label>
                <div className="flex items-center space-x-2">
                  <Input
                    id="threshold"
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={threshold}
                    onChange={(e) => {
                      const value = parseFloat(e.target.value);
                      if (!isNaN(value) && value >= 0 && value <= 1) {
                        setThreshold(value);
                      }
                    }}
                    disabled={isUploading}
                    className="w-32"
                  />
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={[threshold]}
                    onValueChange={(value) => setThreshold(value[0])}
                    disabled={isUploading}
                    className="flex-1"
                  />
                </div>
                <p className="text-xs text-gray-500">
                  Values above this threshold will be considered as objects
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="minArea">Minimum Area (pixels)</Label>
                <Input
                  id="minArea"
                  type="number"
                  min={1}
                  value={minArea}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      setMinArea(value);
                    }
                  }}
                  disabled={isUploading}
                  className="w-32"
                />
                <p className="text-xs text-gray-500">
                  Objects smaller than this will be filtered out (after hole filling)
                </p>
              </div>
            </>
          )}

          {/* Error Display */}
          {error && (
            <div className="flex items-center space-x-2 text-red-500 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end space-x-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!file || !name.trim() || isUploading}
            >
              {isUploading ? 'Processing...' : 'Upload & Process'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default SegmentationUploadModal;