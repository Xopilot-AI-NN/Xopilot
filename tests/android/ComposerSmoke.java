/*
Файл: /tests/android/ComposerSmoke.java
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Настоящие открытия и закрытия клавиатуры без отправки или изменения черновика.
*/
import com.android.uiautomator.testrunner.UiAutomatorTestCase;
import com.android.uiautomator.core.UiObject;
import com.android.uiautomator.core.UiSelector;

public class ComposerSmoke extends UiAutomatorTestCase {
    private UiObject field() {
        return new UiObject(new UiSelector().className("android.widget.EditText")
            .packageName("by.xopilot.app"));
    }
    public void testKeyboardPreservesDraft() throws Exception {
        String original=field().getText();
        for(int i=0;i<3;i++) {
            assertTrue(field().click());
            getUiDevice().waitForIdle(500);
            assertEquals(original,field().getText());
            getUiDevice().pressBack();
            getUiDevice().waitForIdle(500);
            assertEquals(original,field().getText());
        }
    }
}
