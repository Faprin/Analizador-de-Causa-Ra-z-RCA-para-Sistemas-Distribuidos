package rca.pedidos.api_pedidos.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class RestClientConfig {

    @Value("${url.api.inventario:http://api-inventario:8080/inventario}")
    private String urlInventario;

    @Bean
    public RestClient restClient(RestClient.Builder builder) {

        return builder
                .baseUrl(urlInventario)
                .requestFactory(new HttpComponentsClientHttpRequestFactory() {{
                    setConnectTimeout(Duration.ofSeconds(3));
                    setReadTimeout(Duration.ofSeconds(5));
                }})
                .requestInterceptor((request, body, execution) -> {
                    return execution.execute(request, body);
                })
                .build();
    }
}