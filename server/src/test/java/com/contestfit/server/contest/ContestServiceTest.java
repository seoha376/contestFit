package com.contestfit.server.contest;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ContestServiceTest {
    @Test
    void returnsStoredSeedPayloadsForTheWebDecisionEngine() {
        ContestRepository repository = mock(ContestRepository.class);
        Contest contest = new Contest(
                "테스트 공모전",
                null,
                null,
                "https://example.test/contest",
                ValidationStatus.DRAFT,
                "{\"id\":\"seed-1\",\"title\":\"테스트 공모전\",\"sections\":[]}"
        );
        when(repository.findAllBySeedPayloadIsNotNullOrderByIdAsc()).thenReturn(List.of(contest));

        ContestService service = new ContestService(repository, new ObjectMapper());

        assertThat(service.findSeedFeed()).singleElement().satisfies(feed -> {
            assertThat(feed.path("id").asText()).isEqualTo("seed-1");
            assertThat(feed.path("sections").isArray()).isTrue();
        });
    }
}
