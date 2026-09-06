import { get, put } from './request'

export interface ConfigItem {
  id: number
  config_key: string
  config_name: string
  config_value: string | null
  description: string | null
  updated_at: string
}

export const configApi = {
  list: () => get<ConfigItem[]>('/configs'),
  update: (id: number, data: { config_value?: string; description?: string }) =>
    put<ConfigItem>(`/configs/${id}`, data),
}
