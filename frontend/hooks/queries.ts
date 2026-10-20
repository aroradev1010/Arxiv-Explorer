"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
export const useCategories = () =>
  useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => api.categories(signal),
    staleTime: 3600000,
  });
export const useStats = () =>
  useQuery({
    queryKey: ["stats"],
    queryFn: ({ signal }) => api.stats(signal),
    staleTime: 300000,
  });
