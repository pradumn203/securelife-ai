import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type ChatSessionOut, type LeadDetailOut } from './client'

export const leadDetailKey = (leadId: string | null) => ['prospect-lead', leadId] as const

export function useStartSession() {
  return useMutation<ChatSessionOut, Error, void>({
    mutationFn: () => api.createSession('WEB'),
  })
}

export function useLeadDetail(leadId: string | null) {
  return useQuery<LeadDetailOut>({
    queryKey: leadDetailKey(leadId),
    queryFn: () => {
      if (!leadId) throw new Error('leadId required')
      return api.getLead(leadId)
    },
    enabled: !!leadId,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
  })
}

export function useInvalidateLeadDetail() {
  const queryClient = useQueryClient()
  return (leadId: string) => queryClient.invalidateQueries({ queryKey: leadDetailKey(leadId) })
}
