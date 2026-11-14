// Цикл Live отделён от UI: проверяю порядок стадий и отмену без записи комнаты пользователя.
use anyhow::Result;
use tokio_util::sync::CancellationToken;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Listening,
    Recognizing,
    Answering,
    Speaking,
}

pub trait Client {
    fn active(&self) -> bool;
    fn phase(&mut self, phase: Phase);
    fn listen(
        &mut self,
        token: CancellationToken,
    ) -> impl Future<Output = Result<Vec<u8>>>;
    fn recognize(
        &mut self,
        audio: Vec<u8>,
        token: CancellationToken,
    ) -> impl Future<Output = Result<String>>;
    fn answer(
        &mut self,
        text: String,
        token: CancellationToken,
    ) -> impl Future<Output = Result<String>>;
    fn speak(
        &mut self,
        text: String,
        token: CancellationToken,
    ) -> impl Future<Output = Result<()>>;
}

/// Следующий микрофон открываю только после окончания предыдущего ответа и голоса.
pub async fn run(
    client: &mut impl Client,
    token: CancellationToken,
) -> Result<()> {
    while client.active() && !token.is_cancelled() {
        client.phase(Phase::Listening);
        let audio =
            client.listen(token.child_token()).await?;
        if token.is_cancelled() || !client.active() {
            break;
        }
        client.phase(Phase::Recognizing);
        let text = client
            .recognize(audio, token.child_token())
            .await?;
        if token.is_cancelled() || !client.active() {
            break;
        }
        anyhow::ensure!(
            !text.trim().is_empty(),
            "Речь не распознана. Попробуйте включить Live ещё раз"
        );
        client.phase(Phase::Answering);
        let reply = client
            .answer(text, token.child_token())
            .await?;
        if token.is_cancelled() || !client.active() {
            break;
        }
        anyhow::ensure!(
            !reply.trim().is_empty(),
            "ИИ не вернул текст для озвучивания"
        );
        client.phase(Phase::Speaking);
        client.speak(reply, token.child_token()).await?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Fixture {
        events: Vec<Phase>,
        turns: usize,
        fail: Option<Phase>,
        cancel: Option<CancellationToken>,
    }
    impl Client for Fixture {
        fn active(&self) -> bool {
            self.turns < 2
        }
        fn phase(&mut self, p: Phase) {
            self.events.push(p);
        }
        async fn listen(
            &mut self,
            _: CancellationToken,
        ) -> Result<Vec<u8>> {
            if self.fail == Some(Phase::Listening) {
                anyhow::bail!("Микрофон не разрешён")
            };
            Ok(vec![1])
        }
        async fn recognize(
            &mut self,
            audio: Vec<u8>,
            _: CancellationToken,
        ) -> Result<String> {
            assert_eq!(audio, vec![1]);
            if self.fail == Some(Phase::Recognizing) {
                anyhow::bail!("Ошибка ASR")
            };
            if let Some(t) = &self.cancel {
                t.cancel();
            }
            Ok("Реплика".into())
        }
        async fn answer(
            &mut self,
            text: String,
            _: CancellationToken,
        ) -> Result<String> {
            assert_eq!(text, "Реплика");
            if self.fail == Some(Phase::Answering) {
                anyhow::bail!("Ошибка модели")
            };
            Ok("Ответ".into())
        }
        async fn speak(
            &mut self,
            text: String,
            _: CancellationToken,
        ) -> Result<()> {
            assert_eq!(text, "Ответ");
            if self.fail == Some(Phase::Speaking) {
                anyhow::bail!("Нет голоса")
            };
            self.turns += 1;
            Ok(())
        }
    }
    /// Два оборота проходят полностью; слушание не запускается во время собственного голоса.
    #[tokio::test]
    async fn alternates_input_and_output() {
        let mut f = Fixture {
            events: vec![],
            turns: 0,
            fail: None,
            cancel: None,
        };
        run(&mut f, CancellationToken::new())
            .await
            .unwrap();
        assert_eq!(
            f.events,
            [
                Phase::Listening,
                Phase::Recognizing,
                Phase::Answering,
                Phase::Speaking
            ]
            .repeat(2)
        );
    }
    /// Ошибка любой стадии не приводит к запуску последующих действий.
    #[tokio::test]
    async fn stage_failure_stops_following_work() {
        for (index, phase) in [
            Phase::Listening,
            Phase::Recognizing,
            Phase::Answering,
            Phase::Speaking,
        ]
        .into_iter()
        .enumerate()
        {
            let mut f = Fixture {
                events: vec![],
                turns: 0,
                fail: Some(phase),
                cancel: None,
            };
            assert!(
                run(&mut f, CancellationToken::new())
                    .await
                    .is_err()
            );
            assert_eq!(f.events.len(), index + 1);
        }
    }
    /// Отменённая расшифровка не становится запросом к агенту.
    #[tokio::test]
    async fn cancel_before_answer_does_not_send() {
        let token = CancellationToken::new();
        let mut f = Fixture {
            events: vec![],
            turns: 0,
            fail: None,
            cancel: Some(token.clone()),
        };
        run(&mut f, token).await.unwrap();
        assert_eq!(
            f.events,
            [Phase::Listening, Phase::Recognizing]
        );
    }
}
