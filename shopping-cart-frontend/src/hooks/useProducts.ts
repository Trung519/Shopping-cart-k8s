import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { productService, type GetProductsParams } from '@/services/productService'
import type { ProductFormInput } from '@/types'

export function useProducts(params: GetProductsParams = {}) {
  return useQuery({
    queryKey: ['products', params],
    queryFn: () => productService.getProducts(params),
  })
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ['product', id],
    queryFn: () => productService.getProductById(id),
    enabled: !!id,
  })
}

export function useCategories(includeInactive = false) {
  return useQuery({
    queryKey: ['categories', includeInactive],
    queryFn: () => productService.getCategories(includeInactive),
  })
}

export function useManageCategories() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['categories'] })
  return {
    create: useMutation({ mutationFn: productService.createCategory, onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, input }: { id: number; input: { name?: string; sortOrder?: number; isActive?: boolean } }) => productService.updateCategory(id, input), onSuccess: refresh }),
    remove: useMutation({ mutationFn: productService.deleteCategory, onSuccess: refresh }),
  }
}

export function useCreateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: ProductFormInput) => productService.createProduct(input),
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      queryClient.setQueryData(['product', product.id], product)
    },
  })
}

export function useUpdateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ProductFormInput }) =>
      productService.updateProduct(id, input),
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      queryClient.setQueryData(['product', product.id], product)
    },
  })
}

export function useDeleteProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => productService.deleteProduct(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      queryClient.removeQueries({ queryKey: ['product', id] })
    },
  })
}
