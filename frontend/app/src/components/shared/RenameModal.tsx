import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/shared/ui/dialog';
import { Button } from '@/components/shared/ui/button';
import { Input } from '@/components/shared/ui/input';
import { Label } from '@/components/shared/ui/label';

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentName: string;
  onSubmit: (newName: string) => void;
}

const RenameModal: React.FC<RenameModalProps> = ({
  isOpen,
  onClose,
  currentName,
  onSubmit,
}) => {
  const [name, setName] = useState(currentName);

  // Update the name when currentName prop changes
  useEffect(() => {
    setName(currentName);
  }, [currentName]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      return;
    }

    onSubmit(name.trim());
    onClose();
  };

  const handleClose = () => {
    // Reset to current name when closing without submitting
    setName(currentName);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Rename</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter new name"
              autoFocus
            />
          </div>

          <div className="flex justify-end space-x-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!name.trim()}
            >
              Rename
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default RenameModal;
