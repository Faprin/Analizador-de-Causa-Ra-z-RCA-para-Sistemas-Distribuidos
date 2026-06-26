package rca.pedidos.api_pedidos.services;

import lombok.AllArgsConstructor;
import org.springframework.http.HttpHeaders;
import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

import rca.pedidos.api_pedidos.models.Pedido;
import rca.pedidos.api_pedidos.models.payload.ProductoResponse;
import rca.pedidos.api_pedidos.repository.PedidoRepository;

@Service
@Validated
@AllArgsConstructor
public class PedidoService {

    private final PedidoRepository pedidoRepository;
    private final RestClient restClient;

    public List<Pedido> obtenerTodosLosPedidos() {
        return pedidoRepository.findAll();
    }

    public Pedido obtenerPedidoPorId(Long id) {
        return pedidoRepository.findById(id).orElse(null);
    }

    public Pedido crearPedido(Pedido pedido, String authHeader) {
        retirarStockeDeInventario(pedido.getProductoId(), pedido.getCantidad(), authHeader);
        
        return pedidoRepository.save(pedido);
    }

    public void eliminarPedido(Long id) {
        pedidoRepository.deleteById(id);
    }

    public ProductoResponse retirarStockeDeInventario(Long idProducto, int cantidad, String authHeader) {
        try {

            return restClient.post()
            .uri("/{id}/retirar?cantidad={cantidad}", idProducto, cantidad)
            .header(HttpHeaders.AUTHORIZATION, authHeader)
            .retrieve()
            .body(ProductoResponse.class);

        } catch(HttpClientErrorException e) {
            throw new ResponseStatusException(
                e.getStatusCode(),
                "Error desde inventario: " + e.getResponseBodyAsString()
            );
        }
    }
}
