package rca.inventario.api_inventario.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import rca.inventario.api_inventario.models.Producto;

public interface ProductoRepository extends JpaRepository<Producto, Long> {

}
