/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";
import { Link } from "@tanstack/react-router";
import api from "../../api/api";
import { TrashIcon } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";


const STATUS_PRIORITY_MAP: { [key: string]: number } = {
  "NEED_USER_ALIGNMENT": -2,
  "USER_ROUGH_ALIGNMENT": 2,
  "REGISTERING": 5,
  "NO_CELLS": 6,
  "DEWARP PENDING": 3,
  "AWAITING_REGISTRATION": -1
}
const MIMSImageSet = ({ mimsImageSet, onSelect }: { mimsImageSet: any, onSelect: any }) => {
  const queryClient = useQueryClient();
  const handleDeleteMimsSet = (imageSetId: string) => {
    console.log("?")
    api.delete(`/mims_image_set/${imageSetId}/`).then(() => queryClient.invalidateQueries());
  }
  return (
    <div className="flex flex-col">
      <div className="flex gap-1 items-center">
        <div className="flex gap-1 items-center" onClick={() => onSelect(mimsImageSet.id)}><div>{mimsImageSet.name || mimsImageSet.id}</div>
          <div>{mimsImageSet?.status}</div>
          <div>{mimsImageSet.mims_images?.length | 0} images</div>
        </div>
        <div className="flex gap-1 items-center">
          <button onClick={() => handleDeleteMimsSet(mimsImageSet.id)}>
          <TrashIcon />
        </button></div>
      </div>
      {mimsImageSet?.status !== 'ALIGNED' ? (mimsImageSet.mims_images?.sort((a: any, b: any) => {
        const a_priority = STATUS_PRIORITY_MAP[a.status as string];
        const b_priority = STATUS_PRIORITY_MAP[b.status as string];
        return (a_priority <= b_priority ? -1 : 1); 
      }).map((mimsImage: any) => (
        <div key={mimsImage.id} className="flex items-center gap-2">
          <Link to={`/mims_image/${mimsImage.id}`}>
            {extractFileName(mimsImage.file)}
          </Link>
          <button>{mimsImage.status}</button>
        </div>
      ))) : null}
    </div>
  );
};

const extractFileName = (url: string) => {
  const parts = url.split('/');
  const fileName = parts[parts.length - 1];
  return fileName.split('.')[0]; // remove extension
};

export default MIMSImageSet;
