import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sellerService, type SellerApplicationStatus } from '@/services/sellerService'

const sellerKeys = { mine: ['seller', 'mine'] as const, applications: ['seller', 'applications'] as const }

export const useMySellerApplication = () => useQuery({ queryKey: sellerKeys.mine, queryFn: sellerService.getMine })
export const useSellerApplications = (status?: SellerApplicationStatus) => useQuery({ queryKey: [...sellerKeys.applications, status], queryFn: () => sellerService.list(status) })
export const useSubmitSellerApplication = () => {
  const client = useQueryClient()
  return useMutation({ mutationFn: sellerService.apply, onSuccess: (application) => client.setQueryData(sellerKeys.mine, application) })
}
export const useReviewSellerApplication = () => {
  const client = useQueryClient()
  return useMutation({ mutationFn: ({ id, status, reason }: { id: string; status: 'APPROVED' | 'REJECTED'; reason?: string }) => sellerService.review(id, status, reason), onSuccess: () => client.invalidateQueries({ queryKey: sellerKeys.applications }) })
}
