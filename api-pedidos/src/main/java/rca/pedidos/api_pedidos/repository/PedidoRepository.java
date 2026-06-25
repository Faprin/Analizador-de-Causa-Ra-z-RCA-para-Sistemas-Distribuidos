package rca.pedidos.api_pedidos.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import rca.pedidos.api_pedidos.models.Pedido;

public interface PedidoRepository extends JpaRepository<Pedido, Long> {

}
