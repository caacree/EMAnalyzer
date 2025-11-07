/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import { useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";

import DetailAligned from "./DetailAligned";
import RegisterImages from "./RegisterImages";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const MimsImage = () => {

  const [isRegistering, setIsRegistering] = useState(false);

  const { mimsImageId } = useParams({ strict: false });
  const { data: mimsImage } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });
  
  const showRegister = mimsImage?.status.toLowerCase() !== "registered" || isRegistering;
  if (!mimsImage) {
    return <div>Loading...</div>;
  }
  
  if (!showRegister) {
    return <DetailAligned isRegistering={isRegistering} setIsRegistering={setIsRegistering} />
  }
  
  return (
    <RegisterImages isRegistering={isRegistering} setIsRegistering={setIsRegistering} />
  );
};

export default MimsImage;
