import type { PageResult } from '@/types'
import { get, post, put, del } from './request'

export interface ProductItem {
  id: number
  name: string
  category: string | null
  price: number | null
  stock: number | null
  description: string | null
  status: number
  status_label: string
  created_at: string
  updated_at: string
}

export interface ProductPayload {
  name: string
  category?: string
  price?: number
  stock?: number
  description?: string
  status: number
}

export interface ProductListParams {
  keyword?: string
  status?: number
  page?: number
  page_size?: number
}

export const PRODUCT_STATUS_OPTIONS = [
  { value: 1, label: '上架' },
  { value: 0, label: '下架' },
]

export const productApi = {
  list: (params: ProductListParams) => get<PageResult<ProductItem>>('/products', { params }),
  create: (data: ProductPayload) => post<ProductItem>('/products', data),
  update: (id: number, data: ProductPayload) => put<ProductItem>(`/products/${id}`, data),
  remove: (id: number) => del(`/products/${id}`),
}
