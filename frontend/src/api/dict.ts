import { get, post, put, del } from './request'

export interface DictTypeItem {
  id: number
  dict_name: string
  dict_code: string
  description: string | null
  status: number
  item_count: number
  created_at: string
}

export interface DictItem {
  id: number
  dict_code: string
  item_label: string
  item_value: string
  sort_order: number
  status: number
}

export const dictApi = {
  listTypes: () => get<DictTypeItem[]>('/dict-types'),
  createType: (data: { dict_name: string; dict_code: string; description?: string }) =>
    post<DictTypeItem>('/dict-types', data),
  updateType: (id: number, data: { dict_name?: string; description?: string; status?: number }) =>
    put<DictTypeItem>(`/dict-types/${id}`, data),
  removeType: (id: number) => del(`/dict-types/${id}`),
  listItems: (typeId: number) => get<DictItem[]>(`/dict-types/${typeId}/items`),
  createItem: (typeId: number, data: { item_label: string; item_value: string; sort_order?: number }) =>
    post<DictItem>(`/dict-types/${typeId}/items`, data),
  updateItem: (itemId: number, data: { item_label?: string; item_value?: string; sort_order?: number; status?: number }) =>
    put<DictItem>(`/dict-types/items/${itemId}`, data),
  removeItem: (itemId: number) => del(`/dict-types/items/${itemId}`),
}
