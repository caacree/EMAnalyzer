/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";
import { Link } from "@tanstack/react-router";

const MIMSImageSet = ({ mimsImageSet, onSelect }: { mimsImageSet: any, onSelect: any }) => {
  return (
    <div onClick={() => onSelect(mimsImageSet.id)}>
      <p>{mimsImageSet.name || mimsImageSet.id} - {mimsImageSet.mims_images?.length | 0} images</p>
      {mimsImageSet.mims_images?.map((mimsImage: any) => (
        <div key={mimsImage.id}>
          <Link to={`/mims_image/${mimsImage.id}`}>
            {extractFileName(mimsImage.file)}
          </Link>
        </div>
      ))}
    </div>
  );
};

const extractFileName = (url: string) => {
  const parts = url.split('/');
  const fileName = parts[parts.length - 1];
  return fileName.split('.')[0]; // remove extension
};

export default MIMSImageSet;
